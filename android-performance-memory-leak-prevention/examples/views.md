# Samples: Views and XML

## Contents
- Fragment binding
- Binding delegate
- Observing with the view lifecycle
- Presenter attach and detach
- Custom view registration
- Handler versus lifecycleScope
- Activity result launcher
- NavController listener
- Choreographer frame callback
- TypedArray
- WebView teardown

## Fragment binding

```kotlin
class HomeFragment : Fragment(R.layout.fragment_home) {
    private var _binding: FragmentHomeBinding? = null
    private val binding get() = _binding!!

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        _binding = FragmentHomeBinding.bind(view)
        binding.list.adapter = adapter
    }

    override fun onDestroyView() {
        binding.list.adapter = null   // adapter is a Fragment field; drop its view references
        _binding = null
        super.onDestroyView()
    }
}
```

## Binding delegate

```kotlin
fun <T : ViewBinding> Fragment.viewBinding(bind: (View) -> T) =
    object : ReadOnlyProperty<Fragment, T> {
        private var value: T? = null
        init {
            viewLifecycleOwnerLiveData.observe(this@viewBinding) { owner ->
                owner?.lifecycle?.addObserver(object : DefaultLifecycleObserver {
                    override fun onDestroy(o: LifecycleOwner) { value = null }
                })
            }
        }
        override fun getValue(thisRef: Fragment, property: KProperty<*>): T =
            value ?: bind(requireView()).also { value = it }
    }

class HomeFragment : Fragment(R.layout.fragment_home) {
    private val binding by viewBinding(FragmentHomeBinding::bind)
}
```

## Observing with the view lifecycle

```kotlin
override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
    viewModel.items.observe(viewLifecycleOwner) { render(it) }
    viewLifecycleOwner.lifecycleScope.launch {
        viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
            viewModel.state.collect { render(it) }
        }
    }
}
```

## Presenter attach and detach

```kotlin
class AccountsActivity : AppCompatActivity(), AccountsView {
    @Inject lateinit var presenter: AccountsPresenter      // scoped to this Activity, not wider

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        presenter.attach(this)
    }

    override fun onDestroy() {
        presenter.detach()                                  // nulls its view reference
        super.onDestroy()
    }
}
```

## Custom view registration

```kotlin
class HeaderView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null,
) : FrameLayout(context, attrs) {
    private val listener = SessionManager.Listener { session -> render(session) }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        SessionManager.addListener(listener)
    }

    override fun onDetachedFromWindow() {
        SessionManager.removeListener(listener)
        animator?.cancel()
        super.onDetachedFromWindow()
    }
}
```

## Handler versus lifecycleScope

```kotlin
// ❌ Leaks the Activity for 8 s if the user leaves
handler.postDelayed({ advance() }, 8_000)

// ✅ Cancelled on destroy
lifecycleScope.launch { delay(8_000); advance() }
```

## Activity result launcher

```kotlin
class ProfileFragment : Fragment() {
    private val pickAvatar = registerForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        uri?.let(viewModel::setAvatar)
    }
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        binding.avatar.setOnClickListener { pickAvatar.launch(PickVisualMediaRequest()) }
    }
}
```

## NavController listener

```kotlin
private val destinationListener = NavController.OnDestinationChangedListener { _, dest, _ -> updateToolbar(dest) }

override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
    findNavController().addOnDestinationChangedListener(destinationListener)
}
override fun onDestroyView() {
    findNavController().removeOnDestinationChangedListener(destinationListener)
    super.onDestroyView()
}
```

## Choreographer frame callback

```kotlin
class FpsMonitorFragment : Fragment() {
    private var running = false
    private val frameCallback = object : Choreographer.FrameCallback {
        override fun doFrame(frameTimeNanos: Long) {
            record(frameTimeNanos)
            if (running) Choreographer.getInstance().postFrameCallback(this)
        }
    }
    override fun onResume() { super.onResume(); running = true; Choreographer.getInstance().postFrameCallback(frameCallback) }
    override fun onPause() { running = false; Choreographer.getInstance().removeFrameCallback(frameCallback); super.onPause() }
}
```

## TypedArray

```kotlin
init {
    context.obtainStyledAttributes(attrs, R.styleable.RatingBarView).use { ta ->  // androidx.core.content.res.use
        starColor = ta.getColor(R.styleable.RatingBarView_starColor, Color.YELLOW)
    }
}
```

## WebView teardown

```kotlin
override fun onDestroy() {
    binding.webView.apply {
        (parent as? ViewGroup)?.removeView(this)
        stopLoading()
        removeAllViews()
        destroy()
    }
    super.onDestroy()
}
```
