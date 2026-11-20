package com.example.gallery

class GalleryFragment : Fragment(R.layout.fragment_gallery) {
    private var _binding: FragmentGalleryBinding? = null
    private val binding get() = _binding!!
    private val viewModel: GalleryViewModel by viewModels()
    private val adapter = GalleryAdapter()

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        _binding = FragmentGalleryBinding.bind(view)
        binding.grid.adapter = adapter
        binding.refresh.setOnClickListener { viewModel.refresh() }

        val loader = ImageLoader.get(requireContext().applicationContext)
        adapter.loader = loader

        viewModel.title.observe(viewLifecycleOwner) { binding.toolbar.title = it }

        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.pages.collect { page -> adapter.submitList(page.items) }
            }
        }
    }

    override fun onDestroyView() {
        binding.grid.adapter = null
        _binding = null
        super.onDestroyView()
    }
}
