/**
 * Photo Draft Storage & Mobile Resilient Manager - Hub de Desapego
 * 
 * Resolve o problema de recarregamento do navegador móvel (LMK - Low Memory Killer)
 * ao abrir a câmera nativa persistindo fotos e estado no IndexedDB e comprimindo
 * imagens para evitar estouro de memória RAM em smartphones.
 */

const PhotoDraftStorage = {
    DB_NAME: 'DesapegoDraftDB',
    DB_VERSION: 1,
    STORE_PHOTOS: 'draft_photos',
    db: null,

    async openDB() {
        if (this.db) return this.db;

        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.DB_NAME, this.DB_VERSION);

            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                if (!db.objectStoreNames.contains(this.STORE_PHOTOS)) {
                    db.createObjectStore(this.STORE_PHOTOS, { keyPath: 'id', autoIncrement: true });
                }
            };

            request.onsuccess = (event) => {
                this.db = event.target.result;
                resolve(this.db);
            };

            request.onerror = (event) => {
                console.error('Erro ao abrir IndexedDB:', event.target.error);
                reject(event.target.error);
            };
        });
    },

    /**
     * Comprime imagens no cliente para evitar estouro de memória no celular (OOM)
     * e acelerar o upload. Reduz de ~15MB para ~600KB mantendo resolução HD ideal para IA.
     */
    async compressImage(file, maxDimension = 1920, quality = 0.85) {
        // Se não for imagem, retorna o arquivo original
        if (!file.type.startsWith('image/')) return file;

        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                const img = new Image();
                img.onload = () => {
                    let width = img.width;
                    let height = img.height;

                    if (width > maxDimension || height > maxDimension) {
                        if (width > height) {
                            height = Math.round((height * maxDimension) / width);
                            width = maxDimension;
                        } else {
                            width = Math.round((width * maxDimension) / height);
                            height = maxDimension;
                        }
                    }

                    const canvas = document.createElement('canvas');
                    canvas.width = width;
                    canvas.height = height;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);

                    canvas.toBlob(
                        (blob) => {
                            if (!blob) {
                                resolve(file);
                                return;
                            }
                            const compressedFile = new File([blob], file.name.replace(/\.[^/.]+$/, "") + ".jpg", {
                                type: 'image/jpeg',
                                lastModified: Date.now(),
                            });
                            resolve(compressedFile);
                        },
                        'image/jpeg',
                        quality
                    );
                };
                img.onerror = () => resolve(file);
                img.src = e.target.result;
            };
            reader.onerror = () => resolve(file);
            reader.readAsDataURL(file);
        });
    },

    async savePhoto(file, isCover = false) {
        const db = await this.openDB();
        const compressed = await this.compressImage(file);

        return new Promise((resolve, reject) => {
            const tx = db.transaction(this.STORE_PHOTOS, 'readwrite');
            const store = tx.objectStore(this.STORE_PHOTOS);

            const record = {
                file: compressed,
                name: compressed.name,
                type: compressed.type,
                size: compressed.size,
                isCover: isCover,
                createdAt: Date.now()
            };

            const req = store.add(record);
            req.onsuccess = (e) => {
                record.id = e.target.result;
                resolve(record);
            };
            req.onerror = (e) => reject(e.target.error);
        });
    },

    async getAllPhotos() {
        const db = await this.openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(this.STORE_PHOTOS, 'readonly');
            const store = tx.objectStore(this.STORE_PHOTOS);
            const req = store.getAll();

            req.onsuccess = () => resolve(req.result || []);
            req.onerror = (e) => reject(e.target.error);
        });
    },

    async deletePhoto(id) {
        const db = await this.openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(this.STORE_PHOTOS, 'readwrite');
            const store = tx.objectStore(this.STORE_PHOTOS);
            const req = store.delete(id);

            req.onsuccess = () => resolve(true);
            req.onerror = (e) => reject(e.target.error);
        });
    },

    async setCoverPhoto(id) {
        const photos = await this.getAllPhotos();
        const db = await this.openDB();

        return new Promise((resolve, reject) => {
            const tx = db.transaction(this.STORE_PHOTOS, 'readwrite');
            const store = tx.objectStore(this.STORE_PHOTOS);

            photos.forEach(photo => {
                photo.isCover = (photo.id === id);
                store.put(photo);
            });

            tx.oncomplete = () => resolve(true);
            tx.onerror = (e) => reject(e.target.error);
        });
    },

    async clearAll() {
        try {
            const db = await this.openDB();
            const tx = db.transaction(this.STORE_PHOTOS, 'readwrite');
            const store = tx.objectStore(this.STORE_PHOTOS);
            store.clear();
            localStorage.removeItem('desapego_draft_form');
        } catch (e) {
            console.warn('Erro ao limpar rascunho:', e);
        }
    },

    saveFormState(data) {
        try {
            localStorage.setItem('desapego_draft_form', JSON.stringify(data));
        } catch (e) {
            console.warn('Falha ao salvar form no localStorage:', e);
        }
    },

    getFormState() {
        try {
            const data = localStorage.getItem('desapego_draft_form');
            return data ? JSON.parse(data) : null;
        } catch (e) {
            return null;
        }
    }
};
