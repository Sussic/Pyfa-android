package io.github.sussic.pyfa

/** Incoming rows retain their own type and stable identity family. The server owns similar membership. */
internal object ProjectedFighterSelection {
    fun rows(value: FighterSimilarSelection, details: ProjectedFighterDetails, main: ProjectedFighterRow): List<ProjectedFighterRow> = with(OfflineFeatureCodec) {
        expect(!details.isStructure && main.editable && details.squadrons.any { it === main }, "stale incoming reference fighter")
        expect(value.fitId == details.fitId && value.revision == details.revision, "stale incoming fighter selection")
        expect(value.main == FighterSelectionIdentity(main.index, main.objectKey, main.itemId), "different incoming reference fighter")
        expect(value.matches.size in 1..1024 && value.matches.any { it == value.main }, "invalid similar incoming fighter count")
        expect(value.matches.zipWithNext().all { (a, b) -> a.index < b.index } &&
            value.matches.map { it.objectKey }.distinct().size == value.matches.size, "duplicate or unordered incoming selection")
        frozen(value.matches.map { match ->
            val row = details.squadrons.getOrNull(match.index)
            expect(row != null && row.editable && row.index == match.index && row.objectKey == match.objectKey && row.itemId == match.itemId,
                "incoming fighter selection no longer matches its details")
            row!!
        })
    }
}
