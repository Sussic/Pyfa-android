package io.github.sussic.pyfa

import android.text.Html
import android.text.SpannableStringBuilder
import android.text.style.ImageSpan

/** Native plain copy text; paragraph boundaries and Unicode remain intact. */
internal fun inspectionPlainText(html: String?, traits: Boolean): String? {
    if (html.isNullOrEmpty()) return null
    val input = if (traits) html else html.replace("\n", "<br>")
    val text = SpannableStringBuilder(Html.fromHtml(input, Html.FROM_HTML_MODE_COMPACT))
    // Remove actual image cells, retaining literal U+FFFC text characters.
    for (image in text.getSpans(0, text.length, ImageSpan::class.java).sortedByDescending { text.getSpanStart(it) }) {
        text.delete(text.getSpanStart(image), text.getSpanEnd(image))
    }
    return text.toString()
        .replace("\r\n", "\n").trim().replace(Regex("\n{2,}"), "\n")
}
