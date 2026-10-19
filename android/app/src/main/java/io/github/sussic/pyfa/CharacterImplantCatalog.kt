package io.github.sussic.pyfa

/** Complete pinned eligibility metadata, not a fit-local options result or a public market filter. */
data class CharacterImplantItem(val itemId: Int, val name: String, val slot: Int)
data class CharacterImplantCatalog(val datasetSha256: String?, val items: List<CharacterImplantItem>, val error: OfflineFeatureError?) {
    val itemById: Map<Int, CharacterImplantItem> = OfflineFeatureCodec.frozen(items.associateBy { it.itemId })
    fun validate(state: OfflineFeatureState) {
        OfflineFeatureCodec.expect(error == null && datasetSha256 == state.context.datasetSha256, "implant catalogue dataset differs")
        state.profiles.forEach { profile -> profile.implants.forEach { row ->
            val item = itemById[row.itemId]
            OfflineFeatureCodec.expect(item != null && item.name == row.name && item.slot == row.slot, "profile implant metadata differs")
        } }
    }
}
internal object CharacterImplantCatalogCodec {
    fun decode(raw: String, expectedDataset: String): CharacterImplantCatalog = with(OfflineFeatureCodec) {
        expect(raw.toByteArray(Charsets.UTF_8).size <= 524_288, "implant catalogue exceeds 524288 bytes")
        val root = parse(raw); keys(root, "version", "ok", "dataset_sha256", "implants", "error")
        expect(integer(root.get("version")) == 1L, "invalid implant catalogue version")
        val dataset = nullableText(root.get("dataset_sha256"))
        expect(dataset == null || dataset.matches(Regex("[0-9a-f]{64}")) && dataset == expectedDataset, "implant catalogue dataset differs")
        val ok = bool(root.get("ok"))
        val items = rows(root.get("implants")).map { value -> obj(value).let { row ->
            keys(row, "item_id", "name", "slot")
            val id = integer(row.get("item_id")); val slot = integer(row.get("slot"))
            expect(id in 1..Int.MAX_VALUE.toLong() && slot in 1..Int.MAX_VALUE.toLong(), "invalid implant catalogue item or slot")
            val name = text(row.get("name")); expect(name.isNotEmpty() && name.none { Character.isISOControl(it) }, "invalid implant catalogue name")
            CharacterImplantItem(id.toInt(), name, slot.toInt())
        } }
        expect(items.zipWithNext().all { (a, b) -> a.itemId < b.itemId }, "unordered or duplicate catalogue item")
        val error = if (ok) {
            expect(dataset == expectedDataset && root.get("error") === org.json.JSONObject.NULL, "invalid implant catalogue success"); null
        } else {
            expect(items.isEmpty(), "failed implant catalogue contains rows")
            val row = obj(root.get("error")); keys(row, "code", "message")
            val code = text(row.get("code")); expect(code.matches(Regex("[a-z][a-z0-9_]{0,63}")), "invalid catalogue error code")
            OfflineFeatureError(code, safeText(row.get("message"), 1024))
        }
        CharacterImplantCatalog(dataset, frozen(items), error)
    }
}
