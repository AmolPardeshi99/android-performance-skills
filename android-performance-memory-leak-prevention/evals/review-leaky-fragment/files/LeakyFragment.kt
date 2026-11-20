package com.example.orders

class OrdersFragment : Fragment(R.layout.fragment_orders) {
    private lateinit var binding: FragmentOrdersBinding
    private val disposables = CompositeDisposable()
    private val handler = Handler(Looper.getMainLooper())

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        binding = FragmentOrdersBinding.bind(view)
        SessionManager.addListener { session -> binding.title.text = session.userName }
        viewModel.orders.observe(this) { adapter.submitList(it) }
        disposables.add(repo.liveOrders().subscribe { binding.count.text = it.size.toString() })
        handler.postDelayed({ binding.banner.isVisible = true }, 10_000)
        val launcher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { refresh() }
        binding.add.setOnClickListener { launcher.launch(Intent(requireContext(), AddOrderActivity::class.java)) }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        // TODO cleanup
    }
}
