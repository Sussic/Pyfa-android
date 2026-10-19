package io.github.sussic.pyfa

/** Membership comes from the original EOS/source predicate, never implemented-ability UI rows. */
data class FighterSelectionIdentity(val index: Int, val objectKey: String, val itemId: Int)
data class FighterSimilarSelection(val fitId: String, val revision: Long,
    val main: FighterSelectionIdentity, val matches: List<FighterSelectionIdentity>)

internal object FighterSimilarSelectionCodec {
    const val LIMIT_MESSAGE = "Select at most 1024 squadrons per edit"
    private fun index(raw: Any): Int = OfflineFeatureCodec.integer(raw).also {
        OfflineFeatureCodec.expect(it in 0..Int.MAX_VALUE.toLong(), "invalid fighter position")
    }.toInt()
    private fun selectionIdentity(raw: Any): FighterSelectionIdentity = with(OfflineFeatureCodec) {
        val row = obj(raw); keys(row, "index", "object_key", "item_id")
        val itemId = index(row.get("item_id")); expect(itemId > 0, "invalid fighter item")
        FighterSelectionIdentity(index(row.get("index")), identity(row.get("object_key")), itemId)
    }
    fun decode(json: String): FighterSimilarSelection = with(OfflineFeatureCodec) {
        val root = parse(json); keys(root, "version", "fit_id", "revision", "main", "matches")
        expect(integer(root.get("version")) == 1L, "unsupported fighter selection version")
        val revision = integer(root.get("revision")); expect(revision >= 1, "invalid fighter revision")
        val main = selectionIdentity(root.get("main"))
        val rawMatches = rows(root.get("matches"))
        expect(rawMatches.size in 1..1024, "invalid similar fighter count")
        val matches = rawMatches.map(::selectionIdentity)
        expect(matches.zipWithNext().all { (a, b) -> a.index < b.index }, "unordered or duplicate fighter positions")
        expect(matches.map { it.objectKey }.distinct().size == matches.size, "duplicate fighter identity")
        expect(matches.any { it == main }, "missing reference fighter")
        FighterSimilarSelection(identity(root.get("fit_id")), revision, main, frozen(matches))
    }
    /** Correlate every returned position with the exact captured details before publishing selection. */
    fun selectedKeys(value: FighterSimilarSelection, details: FighterDetails, main: FighterSquadron): Set<String> = with(OfflineFeatureCodec) {
        expect(details.squadrons.any { it === main }, "stale reference fighter")
        expect(value.fitId == details.fitId && value.revision == details.revision, "stale fighter selection")
        expect(value.main == FighterSelectionIdentity(main.index, main.objectKey, main.itemId), "different reference fighter")
        expect(value.matches.size in 1..1024 && value.matches.any { it == value.main }, "invalid similar fighter count")
        expect(value.matches.zipWithNext().all { (a, b) -> a.index < b.index } &&
            value.matches.map { it.objectKey }.distinct().size == value.matches.size, "duplicate or unordered fighter selection")
        value.matches.forEach { match ->
            val row = details.squadrons.getOrNull(match.index)
            expect(row != null && row.index == match.index && row.objectKey == match.objectKey && row.itemId == match.itemId,
                "fighter selection no longer matches its details")
        }
        value.matches.map { it.objectKey }.toSet()
    }
    fun failureMessage(failure: Throwable): String {
        // Python can wrap the known refusal. Never display arbitrary exception/trace text.
        var cause: Throwable? = failure
        repeat(8) {
            val current = cause ?: return "Similar squadrons could not be verified. Reload fighters and try again."
            if (current.message?.contains(LIMIT_MESSAGE) == true) return "$LIMIT_MESSAGE."
            cause = current.cause
        }
        return "Similar squadrons could not be verified. Reload fighters and try again."
    }
}
