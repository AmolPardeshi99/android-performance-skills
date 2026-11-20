package com.example.gallery

class GalleryViewModel(
    private val repo: GalleryRepository,
) : ViewModel() {

    // Decoded pages: each holds ~40 thumbnails as Bitmaps.
    val pages = MutableSharedFlow<GalleryPage>(replay = 20)

    val title = MutableLiveData("Gallery")

    private val decodeExecutor = Executors.newFixedThreadPool(12)

    init {
        refresh()
    }

    fun refresh() {
        decodeExecutor.execute {
            repo.loadPages().forEach { raw ->
                val page = GalleryPage(raw.items.map { it.copy(thumb = BitmapFactory.decodeByteArray(it.bytes, 0, it.bytes.size)) })
                pages.tryEmit(page)
            }
        }
    }
}
