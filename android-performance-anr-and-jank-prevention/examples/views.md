# Samples: Views and XML

## Contents
- Defer optional UI with ViewStub
- Deferred widget holder
- Skeleton first, real layout async
- Prewarm custom view classes
- Factory2 without reflection
- Cached Typeface in a text component
- RecyclerView binding and diffing
- onDraw without allocations
- Flatter layouts

## Defer optional UI with ViewStub

```xml
<ViewStub
    android:id="@+id/stub_fab"
    android:layout="@layout/view_floating_action"
    android:inflatedId="@+id/fab_root"
    android:layout_width="wrap_content"
    android:layout_height="wrap_content" />
```

```kotlin
private var fab: View? = null   // nullable: absent until activated

private fun activateFab() {
    if (fab == null) fab = binding.stubFab.inflate()
}
```

## Deferred widget holder

```kotlin
class DeferredWidget<T : View>(
    private val container: ViewGroup,
    private val create: (ViewGroup) -> T,
) {
    var view: T? = null
        private set

    fun activate(delayMs: Long = 20) {
        if (view != null) return
        // A short delay lets pending input run before this inflation.
        container.postDelayed({
            if (view == null && container.isAttachedToWindow) {
                view = create(container).also(container::addView)
            }
        }, delayMs)
    }
}

// In the activity: activate after first frame, behind a flag.
override fun onResume() {
    super.onResume()
    if (flags.deferredWidgets) promoWidget.activate() else promoWidget.activate(0)
}
```

## Skeleton first, real layout async

```kotlin
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    val skeleton = ActivityHomeSkeletonBinding.inflate(layoutInflater)
    setContentView(skeleton.root)

    AsyncLayoutInflater(this).inflate(R.layout.activity_home_content, skeleton.contentFrame) { view, _, parent ->
        parent?.addView(view)
        onContentReady(ActivityHomeContentBinding.bind(view))
    }
}
```

`AsyncLayoutInflater` retries on main if background inflation throws, for example for views
that create a `Handler` in their constructor. Check that custom inflater factories and themed
widgets render the same, and test each layout.

## Prewarm custom view classes

```kotlin
object ViewClassPrewarmer {
    // Classes behind the heaviest first-screen layouts. Measure before adding to this list.
    private val classes = listOf(
        "com.example.home.widget.HeaderView",
        "com.example.home.widget.CarouselView",
        "com.example.design.TextLabel",
    )

    fun start(appScope: CoroutineScope, loader: ClassLoader) {
        appScope.launch(Dispatchers.Default) {
            for (name in classes) {
                runCatching { Class.forName(name, true, loader) }
            }
        }
    }
}
```

Call `start` as early as possible (Application or an early provider) so it finishes before the
first inflation.

## Factory2 without reflection

```kotlin
class AppViewFactory : LayoutInflater.Factory2 {
    override fun onCreateView(parent: View?, name: String, context: Context, attrs: AttributeSet): View? =
        when (name) {
            "com.example.design.TextLabel" -> TextLabel(context, attrs)
            "com.example.home.widget.HeaderView" -> HeaderView(context, attrs)
            else -> null   // fall back to the default reflective path
        }

    override fun onCreateView(name: String, context: Context, attrs: AttributeSet): View? =
        onCreateView(null, name, context, attrs)
}
```

With AppCompat, subclass `AppCompatViewInflater`, override `createView` for your own names, and
register it with the `viewInflaterClass` theme attribute, so AppCompat widgets keep working.

## Cached Typeface in a text component

```kotlin
object TypefaceCache {
    private val cache = ConcurrentHashMap<Int, Typeface>()
    fun get(context: Context, @FontRes id: Int): Typeface =
        cache.getOrPut(id) { ResourcesCompat.getFont(context.applicationContext, id)!! }
}

class TextLabel @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null,
) : AppCompatTextView(context, attrs) {
    private var appliedStyle: Int = 0

    fun setLabelStyle(style: LabelStyle) {
        if (style.id == appliedStyle) return          // skip redundant re-application
        typeface = TypefaceCache.get(context, style.fontRes)
        setTextSize(TypedValue.COMPLEX_UNIT_SP, style.sizeSp)
        appliedStyle = style.id
    }
}
```

## RecyclerView binding and diffing

```kotlin
class PostAdapter : ListAdapter<PostUi, PostViewHolder>(PostDiff) {
    override fun onBindViewHolder(holder: PostViewHolder, position: Int) {
        holder.bind(getItem(position))   // PostUi is already formatted; bind only assigns
    }
}

// ViewModel prepares display models off main.
val posts: StateFlow<List<PostUi>> = repo.posts
    .map { list -> list.filter { it.isActive }.map(Post::toUi) }
    .flowOn(Dispatchers.Default)
    .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
```

## onDraw without allocations

```kotlin
class GraphView(context: Context, attrs: AttributeSet?) : View(context, attrs) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.RED }
    private val rect = RectF()

    override fun onDraw(canvas: Canvas) {
        rect.set(0f, 0f, width.toFloat(), height.toFloat())
        canvas.drawRect(rect, paint)
    }
}
```

## Flatter layouts

```xml
<!-- Included into a ConstraintLayout parent: merge removes one level. -->
<merge xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto">
    <ImageView android:id="@+id/icon" ... app:layout_constraintStart_toStartOf="parent" />
    <TextView android:id="@+id/title" ... app:layout_constraintStart_toEndOf="@id/icon" />
</merge>
```

Replace a `LottieAnimationView` that only ever shows a static frame with an `ImageView`.
