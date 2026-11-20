package com.example.home

class HomeActivity : AppCompatActivity() {
    @Inject lateinit var analytics: AnalyticsClient          // builds OkHttp + Gson + DB on first use
    @Inject lateinit var reminder: ReminderScheduler         // reads 3 SharedPreferences files in init
    private val prefs by lazy { getSharedPreferences("home", MODE_PRIVATE) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        (application as ShopApp).component.inject(this)
        setContentView(R.layout.activity_home_everything)

        val config = Gson().fromJson(DEFAULT_CONFIG_JSON, HomeConfig::class.java)
        val country = Gson().fromJson(prefs.getString("geo", "{}"), Geo::class.java).countryCode
        binding.date.text = SimpleDateFormat("dd MMM", Locale.getDefault()).format(Date())

        inboxRepo.unreadCount()
            .subscribeOn(Schedulers.io())
            .observeOn(AndroidSchedulers.mainThread())
            .map { json -> Gson().fromJson(json, Unread::class.java) }
            .subscribe { render(it) }

        val token = runBlocking { authRepo.token() }
        render(config, country, token)
    }

    override fun onResume() {
        super.onResume()
        lifecycleScope.launch {
            val list = withContext(Dispatchers.IO) { repo.items() }
            adapter.submitList(list)
        }
    }

    companion object {
        const val DEFAULT_CONFIG_JSON = """{"tiles":[...],"version":3}"""
    }
}
