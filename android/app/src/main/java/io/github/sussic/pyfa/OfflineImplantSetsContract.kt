package io.github.sussic.pyfa

import org.json.JSONObject

/** Detached ordered recipes. Application never binds a fit/profile to a recipe. */
data class OfflineImplantSetEntry(val id: String, val kind: String, val name: String, val family: String?,
    val grade: String?, val revision: Long, val itemCount: Long) {
    val readonly get() = kind == "builtin"
}
data class OfflineImplantSetItem(val itemId: Int, val name: String, val slot: Int)
data class OfflineImplantSetDetail(val entry: OfflineImplantSetEntry, val items: List<OfflineImplantSetItem>)
data class OfflineImplantCollectionRow(val rowId: String, val itemId: Int, val name: String, val slot: Int, val active: Boolean)
sealed interface OfflineImplantSetDestination {
    val name: String
    val implants: List<OfflineImplantCollectionRow>
    data class Fit(val fitId: String, val fitRevision: Long, override val name: String, val isStructure: Boolean,
        override val implants: List<OfflineImplantCollectionRow>) : OfflineImplantSetDestination
    data class Profile(val profileId: String, val profileRevision: Long, override val name: String, val readonly: Boolean,
        val assignedFitCount: Long, override val implants: List<OfflineImplantCollectionRow>) : OfflineImplantSetDestination
}
data class OfflineImplantSaveSource(val fitId: String, val fitRevision: Long, val source: ImplantLocation,
    val profileId: String?, val profileRevision: Long?, val profileName: String?, val implantCount: Long)
data class OfflineImplantSetView(val query: String = "", val offset: Long = 0, val limit: Int = 50,
    val selectedSetId: String? = null, val targetProfileId: String? = null, val historyTarget: String = "library") {
    fun json(): JSONObject = JSONObject().put("query", query).put("offset", offset).put("limit", limit)
        .put("selected_set_id", selectedSetId ?: JSONObject.NULL).put("target_profile_id", targetProfileId ?: JSONObject.NULL)
        .put("history_target", historyTarget)
}
data class OfflineImplantSetState(val context: OfflineContext, val anchorFitId: String?, val view: OfflineImplantSetView,
    val total: Long, val entries: List<OfflineImplantSetEntry>, val detail: OfflineImplantSetDetail?,
    val destination: OfflineImplantSetDestination?, val saveSource: OfflineImplantSaveSource?, val history: OfflineHistory)
data class OfflineImplantSetRequest(val requestId: String, val context: OfflineContext, val anchorFitId: String?,
    val view: OfflineImplantSetView = OfflineImplantSetView(), val operation: String = "read", val argumentsJson: String = "{}") {
    fun json(): String = OfflineImplantSetsCodec.request(this)
}
data class OfflineImplantSetResponse(val requestId: String, val ok: Boolean, val committed: Boolean?, val reopenRequired: Boolean,
    val state: OfflineImplantSetState?, val bridge: BridgeResponse?, val error: OfflineFeatureError?)

internal object OfflineImplantSetsCodec {
    private fun expect(test: Boolean, message: String) = OfflineFeatureCodec.expect(test, "Implant sets: $message")
    private fun obj(raw: Any) = OfflineFeatureCodec.obj(raw)
    private fun keys(row: JSONObject, vararg names: String) = OfflineFeatureCodec.keys(row, *names)
    private fun text(raw: Any) = OfflineFeatureCodec.text(raw)
    private fun nullableText(raw: Any) = OfflineFeatureCodec.nullableText(raw)
    private fun bool(raw: Any) = OfflineFeatureCodec.bool(raw)
    private fun integer(raw: Any, minimum: Long = 0): Long = OfflineFeatureCodec.integer(raw).also { expect(it >= minimum, "invalid count or revision") }
    private fun itemId(raw: Any): Int = integer(raw, 1).also { expect(it <= Int.MAX_VALUE, "invalid item or slot") }.toInt()
    private fun hex(raw: Any) = OfflineFeatureCodec.hexId(raw)
    private fun profile(raw: Any) = OfflineFeatureCodec.profileId(raw)
    private fun context(raw: Any) = OfflineFeatureCodec.featureContext(obj(raw))
    private fun requestId(raw: Any) = text(raw).also { expect(it.length in 1..128 && it.all { c -> c.code in 32..126 }, "invalid request ID") }
    private fun legacy(raw: Any) = text(raw).also { expect(it.isNotEmpty(), "empty legacy label") }
    private fun safe(raw: Any, limit: Int, allowEmpty: Boolean = false) = text(raw).also { value ->
        expect((allowEmpty || value.isNotEmpty()) && value.codePointCount(0, value.length) <= limit &&
            value.none { Character.isISOControl(it) }, "invalid Unicode text")
    }
    fun cleanText(raw: Any, allowEmpty: Boolean = false) = safe(raw, 200, allowEmpty)
    private fun space(c: Char) = c in '\u0009'..'\u000D' || c in '\u001C'..'\u0020' || c == '\u0085' || c == '\u00A0' ||
        c == '\u1680' || c in '\u2000'..'\u200A' || c == '\u2028' || c == '\u2029' || c == '\u202F' || c == '\u205F' || c == '\u3000'
    fun name(raw: String): String = cleanText(text(raw).trim(::space))
    fun setId(raw: Any): String = text(raw).also { id ->
        val ordinal = id.removePrefix("builtin:implant-set:").toIntOrNull()
        expect(id.matches(Regex("implant-set:[0-9a-f]{32}")) || ordinal != null && ordinal > 0 &&
            id == "builtin:implant-set:$ordinal", "invalid set identity")
    }
    private fun revision(id: String, raw: Any): Long = integer(raw).also {
        expect(if (id.startsWith("builtin:")) it == 0L else it > 0, "invalid set revision")
    }
    private fun profileRevision(id: String, raw: Any): Long = integer(raw).also {
        expect(if (id.startsWith("builtin:")) it == 0L else it > 0, "invalid profile revision")
    }
    private fun historyTarget(raw: Any) = text(raw).also { if (it != "library") hex(it) }
    private fun validateView(view: OfflineImplantSetView, anchor: String?) {
        cleanText(view.query, true); expect(view.offset >= 0 && view.limit in 1..50, "invalid page")
        view.selectedSetId?.let(::setId); view.targetProfileId?.let(::profile); historyTarget(view.historyTarget)
        expect(view.historyTarget == "library" || anchor != null && view.historyTarget == anchor, "history target differs from anchor")
    }
    private fun view(raw: Any): OfflineImplantSetView {
        val row = obj(raw); keys(row, "query", "offset", "limit", "selected_set_id", "target_profile_id", "history_target")
        val limit = integer(row.get("limit"), 1).also { expect(it <= 50, "invalid page limit") }
        return OfflineImplantSetView(cleanText(row.get("query"), true), integer(row.get("offset")), limit.toInt(),
            nullableText(row.get("selected_set_id"))?.let(::setId), nullableText(row.get("target_profile_id"))?.let(::profile), historyTarget(row.get("history_target")))
    }
    private val libraryOperations = setOf("create", "rename", "duplicate", "delete", "add_item", "remove_item", "save_current")
    private val setOperations = setOf("rename", "duplicate", "delete", "add_item", "remove_item", "apply_fit", "apply_profile")
    fun request(value: OfflineImplantSetRequest): String {
        requestId(value.requestId); context(value.context.json()); value.anchorFitId?.let(::hex); validateView(value.view, value.anchorFitId)
        expect(value.argumentsJson.length <= 16_384 && value.argumentsJson.toByteArray(Charsets.UTF_8).size <= 16_384, "request arguments exceed bounds")
        val args = OfflineFeatureCodec.parse(value.argumentsJson)
        fun selected(custom: Boolean = false) {
            val id = setId(args.get("set_id")); revision(id, args.get("revision"))
            expect(id == value.view.selectedSetId, "operation set differs from selected detail")
            if (custom) expect(!id.startsWith("builtin:"), "built-in sets are read-only")
        }
        fun named() { val raw = text(args.get("name")); expect(raw == name(raw), "untrimmed set name") }
        fun fit() { expect(value.anchorFitId != null, "fit required"); integer(args.get("fit_revision"), 1) }
        when (value.operation) {
            "read", "undo", "redo" -> keys(args)
            "create" -> { keys(args, "name"); named() }
            "rename", "duplicate" -> { keys(args, "set_id", "revision", "name"); selected(true); named() }
            "delete" -> { keys(args, "set_id", "revision"); selected(true) }
            "add_item" -> {
                keys(args, "set_id", "revision", "item_id", "replace_item_id"); selected(true); itemId(args.get("item_id"))
                if (args.get("replace_item_id") !== JSONObject.NULL) itemId(args.get("replace_item_id"))
            }
            "remove_item" -> { keys(args, "set_id", "revision", "item_id"); selected(true); itemId(args.get("item_id")) }
            "save_current" -> { keys(args, "name", "fit_revision"); named(); fit() }
            "apply_fit" -> {
                keys(args, "set_id", "revision", "fit_revision"); selected(); fit()
                expect(value.view.targetProfileId == null && value.view.historyTarget == value.anchorFitId, "fit application destination/history differs")
            }
            "apply_profile" -> {
                keys(args, "set_id", "revision", "profile_id", "profile_revision"); selected()
                val id = profile(args.get("profile_id")); expect(!id.startsWith("builtin:"), "built-in character is read-only")
                integer(args.get("profile_revision"), 1)
                expect(id == value.view.targetProfileId && value.view.historyTarget == "library", "character application destination/history differs")
            }
            else -> expect(false, "unknown operation")
        }
        if (value.operation in libraryOperations) expect(value.view.historyTarget == "library", "template changes use library history")
        return OfflineFeatureCodec.json(JSONObject().put("version", 1).put("request_id", value.requestId).put("context", value.context.json())
            .put("anchor_fit_id", value.anchorFitId ?: JSONObject.NULL).put("view", value.view.json())
            .put("operation", value.operation).put("arguments", args)).also {
            expect(it.length <= 16_384 && it.toByteArray(Charsets.UTF_8).size <= 16_384, "request exceeds bounds")
        }
    }
    /** Used by retained-wire checks too: do not reconstruct malformed numeric kinds with getInt/getLong. */
    fun decodeRequest(raw: String): OfflineImplantSetRequest {
        expect(raw.length <= 16_384 && raw.toByteArray(Charsets.UTF_8).size <= 16_384, "request exceeds bounds")
        val row = OfflineFeatureCodec.parse(raw)
        keys(row, "version", "request_id", "context", "anchor_fit_id", "view", "operation", "arguments")
        expect(integer(row.get("version")) == 1L, "unsupported request version")
        return OfflineImplantSetRequest(requestId(row.get("request_id")), context(row.get("context")),
            nullableText(row.get("anchor_fit_id"))?.let(::hex), view(row.get("view")), text(row.get("operation")),
            OfflineFeatureCodec.json(obj(row.get("arguments")))).also { request(it) }
    }
    private fun entry(row: JSONObject, detail: Boolean = false): OfflineImplantSetEntry {
        val metadata = arrayOf("set_id", "kind", "name", "family", "grade", "revision", "item_count")
        keys(row, *(if (detail) metadata + "items" else metadata))
        val id = setId(row.get("set_id")); val kind = text(row.get("kind")); val builtin = id.startsWith("builtin:")
        expect(kind == if (builtin) "builtin" else "custom", "set kind differs")
        val label = cleanText(row.get("name")); val family = nullableText(row.get("family"))?.let { cleanText(it) }
        val grade = nullableText(row.get("grade"))?.let { cleanText(it) }
        if (builtin) expect(family != null && label == if (grade == null) family else "$grade $family", "builtin label differs")
        else expect(label == name(label) && family == null && grade == null, "invalid custom metadata")
        return OfflineImplantSetEntry(id, kind, label, family, grade, revision(id, row.get("revision")), integer(row.get("item_count")))
    }
    private fun detail(raw: Any): OfflineImplantSetDetail {
        val row = obj(raw); val metadata = entry(row, true)
        val items = OfflineFeatureCodec.rows(row.get("items")).map { obj(it).let { item ->
            keys(item, "item_id", "name", "slot")
            OfflineImplantSetItem(itemId(item.get("item_id")), safe(item.get("name"), Int.MAX_VALUE), itemId(item.get("slot")))
        } }
        expect(items.size.toLong() == metadata.itemCount && items.map { it.itemId }.distinct().size == items.size &&
            items.map { it.slot }.distinct().size == items.size, "invalid recipe membership or slots")
        return OfflineImplantSetDetail(metadata, OfflineFeatureCodec.frozen(items))
    }
    private fun collection(raw: Any): List<OfflineImplantCollectionRow> {
        val rows = OfflineFeatureCodec.rows(raw).map { obj(it).let { row ->
            keys(row, "row_id", "item_id", "name", "slot", "active")
            OfflineImplantCollectionRow(hex(row.get("row_id")), itemId(row.get("item_id")), safe(row.get("name"), Int.MAX_VALUE),
                itemId(row.get("slot")), bool(row.get("active")))
        } }
        expect(rows.map { it.rowId }.distinct().size == rows.size && rows.map { it.itemId }.distinct().size == rows.size &&
            rows.map { it.slot }.distinct().size == rows.size, "duplicate collection row, item or slot")
        return OfflineFeatureCodec.frozen(rows)
    }
    private fun destination(raw: Any): OfflineImplantSetDestination {
        val row = obj(raw)
        return when (text(row.get("kind"))) {
            "fit" -> {
                keys(row, "kind", "fit_id", "fit_revision", "name", "is_structure", "implants")
                OfflineImplantSetDestination.Fit(hex(row.get("fit_id")), integer(row.get("fit_revision"), 1), legacy(row.get("name")),
                    bool(row.get("is_structure")), collection(row.get("implants")))
            }
            "profile" -> {
                keys(row, "kind", "profile_id", "profile_revision", "name", "readonly", "assigned_fit_count", "implants")
                val id = profile(row.get("profile_id")); val readonly = bool(row.get("readonly")); val rows = collection(row.get("implants"))
                expect(readonly == id.startsWith("builtin:") && (!readonly || rows.isEmpty()), "modified built-in destination")
                OfflineImplantSetDestination.Profile(id, profileRevision(id, row.get("profile_revision")), legacy(row.get("name")),
                    readonly, integer(row.get("assigned_fit_count")), rows)
            }
            else -> OfflineFeatureCodec.reject("Implant sets: invalid destination kind")
        }
    }
    private fun saveSource(raw: Any): OfflineImplantSaveSource {
        val row = obj(raw)
        keys(row, "fit_id", "fit_revision", "source", "profile_id", "profile_revision", "profile_name", "implant_count")
        val source = OfflineFeatureCodec.source(row.get("source")); val id = nullableText(row.get("profile_id"))?.let(::profile)
        val revision = if (row.get("profile_revision") === JSONObject.NULL) null else {
            expect(id != null, "profile revision without profile"); profileRevision(checkNotNull(id), row.get("profile_revision"))
        }
        val label = if (row.get("profile_name") === JSONObject.NULL) null else legacy(row.get("profile_name"))
        expect(if (source == ImplantLocation.FIT) id == null && revision == null && label == null else id != null && revision != null && label != null,
            "invalid applied-source profile")
        return OfflineImplantSaveSource(hex(row.get("fit_id")), integer(row.get("fit_revision"), 1), source, id, revision, label, integer(row.get("implant_count")))
    }
    private fun history(raw: Any): Pair<String, OfflineHistory> {
        val row = obj(raw); keys(row, "target", "undo_count", "redo_count", "limit", "undo_label", "redo_label")
        val undo = integer(row.get("undo_count")); val redo = integer(row.get("redo_count"))
        expect(integer(row.get("limit")) == 100L && undo <= 100 && redo <= 100 && undo + redo <= 100, "invalid history")
        fun label(key: String, count: Long) = nullableText(row.get(key))?.let { cleanText(it) }.also { expect((it == null) == (count == 0L), "history label differs") }
        return historyTarget(row.get("target")) to OfflineHistory(undo.toInt(), redo.toInt(), 100, label("undo_label", undo), label("redo_label", redo))
    }
    // Python string ordering is Unicode-scalar order, not UTF-16 code-unit ordering.
    private fun compareText(a: String, b: String): Int {
        var x = 0; var y = 0
        while (x < a.length && y < b.length) {
            val ac = a.codePointAt(x); val bc = b.codePointAt(y)
            if (ac != bc) return ac.compareTo(bc)
            x += Character.charCount(ac); y += Character.charCount(bc)
        }
        return (a.length - x).compareTo(b.length - y)
    }
    private fun compareEntry(a: OfflineImplantSetEntry, b: OfflineImplantSetEntry): Int {
        if (a.readonly != b.readonly) return if (a.readonly) -1 else 1
        if (!a.readonly) return compareText(a.name, b.name).takeIf { it != 0 } ?: compareText(a.id, b.id)
        val family = compareText(checkNotNull(a.family), checkNotNull(b.family)); if (family != 0) return family
        fun rank(grade: String?) = when (grade) { "Low-grade" -> 0; "Mid-grade" -> 1; "High-grade" -> 2; else -> 3 }
        val grade = rank(a.grade).compareTo(rank(b.grade)); if (grade != 0) return grade
        return compareText(a.grade ?: "", b.grade ?: "").takeIf { it != 0 } ?: compareText(a.id, b.id)
    }
    private fun state(raw: Any, expected: OfflineImplantSetRequest): OfflineImplantSetState {
        val root = obj(raw); keys(root, "version", "context", "anchor_fit_id", "page", "detail", "destination", "save_source", "history")
        expect(integer(root.get("version")) == 1L, "unsupported state version")
        val ctx = context(root.get("context")); val anchor = nullableText(root.get("anchor_fit_id"))?.let(::hex)
        expect(ctx.sessionId == expected.context.sessionId && ctx.datasetSha256 == expected.context.datasetSha256, "response context differs")
        val replay = expected.operation in setOf("undo", "redo")
        expect(anchor == expected.anchorFitId || replay && anchor == null, "response anchor differs")
        val page = obj(root.get("page")); keys(page, "query", "offset", "limit", "total", "entries")
        expect(cleanText(page.get("query"), true) == expected.view.query && integer(page.get("offset")) == expected.view.offset &&
            integer(page.get("limit"), 1) == expected.view.limit.toLong(), "response page differs")
        val total = integer(page.get("total")); val entries = OfflineFeatureCodec.rows(page.get("entries")).map { entry(obj(it)) }
        expect(entries.size.toLong() == minOf(expected.view.limit.toLong(), if (total > expected.view.offset) total - expected.view.offset else 0), "incomplete page")
        expect(entries.map { it.id }.distinct().size == entries.size && entries.zipWithNext().all { (a, b) -> compareEntry(a, b) < 0 }, "duplicate or unordered page")
        val detail = if (root.get("detail") === JSONObject.NULL) null else detail(root.get("detail"))
        detail?.let { d -> entries.find { it.id == d.entry.id }?.let { expect(it == d.entry, "detail metadata differs") } }
        val target = if (root.get("destination") === JSONObject.NULL) null else destination(root.get("destination"))
        if (expected.view.targetProfileId != null) expect(target == null || target is OfflineImplantSetDestination.Profile && target.profileId == expected.view.targetProfileId, "profile preview target differs")
        else expect(if (anchor == null) target == null else target is OfflineImplantSetDestination.Fit && target.fitId == anchor, "fit preview target differs")
        val source = if (root.get("save_source") === JSONObject.NULL) null else saveSource(root.get("save_source"))
        expect(if (anchor == null) source == null else source != null && source.fitId == anchor, "applied source anchor differs")
        if (target is OfflineImplantSetDestination.Fit) expect(source?.fitRevision == target.fitRevision, "fit preview revision differs")
        val (historyTarget, history) = history(root.get("history"))
        val disappeared = replay && expected.anchorFitId != null && anchor == null
        expect(historyTarget == if (disappeared && expected.view.historyTarget != "library") "library" else expected.view.historyTarget, "history target differs")
        val result = OfflineImplantSetState(ctx, anchor, expected.view.copy(selectedSetId = selectionId(expected, detail), historyTarget = historyTarget), total,
            OfflineFeatureCodec.frozen(entries), detail, target, source, history)
        validateSelection(result, expected)
        return result
    }
    private fun selectionId(request: OfflineImplantSetRequest, detail: OfflineImplantSetDetail?): String? = when (request.operation) {
        "create", "duplicate", "save_current" -> detail?.entry?.id
        "delete" -> null
        else -> request.view.selectedSetId
    }
    private fun validateSelection(state: OfflineImplantSetState, expected: OfflineImplantSetRequest) {
        val detail = state.detail; val args = OfflineFeatureCodec.parse(expected.argumentsJson)
        when (expected.operation) {
            "create", "duplicate", "save_current" -> {
                expect(detail != null && !detail.entry.readonly && detail.entry.revision == 1L && detail.entry.name == text(args.get("name")), "invalid created recipe")
                expect(detail?.entry?.id != expected.view.selectedSetId, "created identity reused selected set")
                if (expected.operation == "create") expect(detail?.items?.isEmpty() == true, "create must be empty")
            }
            "delete" -> expect(detail == null && state.entries.none { it.id == expected.view.selectedSetId }, "deleted set survived")
            in setOperations -> expect(detail != null && detail.entry.id == text(args.get("set_id")), "requested detail missing")
            else -> expect(detail == null || detail.entry.id == expected.view.selectedSetId, "detail was silently retargeted")
        }
        if (expected.operation.startsWith("apply_")) expect(detail?.entry?.revision == integer(args.get("revision")), "application changed recipe revision")
    }
    /** The already-strict parser established syntax. Count the original token span, including escape/whitespace bytes. */
    internal fun stateByteCount(raw: String): Int {
        var position = 0
        fun whitespace() { while (position < raw.length && raw[position] in " \t\r\n") position++ }
        fun stringEnd(): Int {
            position++
            while (position < raw.length) when (raw[position++]) { '\\' -> position++; '"' -> return position }
            return position
        }
        whitespace(); position++
        while (position < raw.length) {
            whitespace(); val keyStart = position; val keyEnd = stringEnd(); val key = StrictJson(raw.substring(keyStart, keyEnd)).parse()
            whitespace(); position++; whitespace(); val start = position; var depth = 0
            while (position < raw.length) {
                val c = raw[position]
                if (c == '"') { stringEnd(); continue }
                if (c == '{' || c == '[') depth++
                if (c == '}' || c == ']') { if (depth == 0) break; depth-- }
                if (c == ',' && depth == 0) break
                position++
            }
            if (key == "state") return raw.substring(start, position).trimEnd(' ', '\t', '\r', '\n').toByteArray(Charsets.UTF_8).size
            if (position < raw.length && raw[position] == ',') position++ else break
        }
        throw BridgeProtocolException("Implant sets: absent state")
    }
    fun response(raw: String, expected: OfflineImplantSetRequest): OfflineImplantSetResponse {
        request(expected)
        val root = OfflineFeatureCodec.parse(raw)
        keys(root, "version", "request_id", "ok", "committed", "reopen_required", "state", "bridge", "error")
        expect(integer(root.get("version")) == 1L && requestId(root.get("request_id")) == expected.requestId, "response identity differs")
        val ok = bool(root.get("ok")); val reopen = bool(root.get("reopen_required"))
        val committed = if (root.get("committed") === JSONObject.NULL) null else bool(root.get("committed"))
        if (!ok) {
            expect(committed != true && (committed == null) == reopen && root.get("state") === JSONObject.NULL && root.get("bridge") === JSONObject.NULL, "partial or ambiguous failure")
            val error = obj(root.get("error")); keys(error, "code", "message")
            val code = text(error.get("code")); expect(code.matches(Regex("[a-z][a-z0-9_]{0,63}")) && (code == "reopen_required") == reopen, "invalid error code")
            return OfflineImplantSetResponse(expected.requestId, false, committed, reopen, null, null, OfflineFeatureError(code, safe(error.get("message"), 1024)))
        }
        expect(committed != null && !reopen && root.get("error") === JSONObject.NULL, "ambiguous success")
        expect(stateByteCount(raw) <= 524_288, "state exceeds 524288 wire bytes")
        val state = state(root.get("state"), expected)
        expect(if (committed == true) expected.context.generation < Long.MAX_VALUE && state.context.generation == expected.context.generation + 1
            else state.context == expected.context, "generation differs")
        val bridge = if (expected.operation == "read") {
            expect(committed == false && root.get("bridge") === JSONObject.NULL, "read mutated or published bridge"); null
        } else BridgeCodec.decodeResponse(OfflineFeatureCodec.json(root.get("bridge"))).also {
            expect(it.isSuccess && it.requestId == "bootstrap" && it.sessionId == state.context.sessionId, "invalid complete bridge")
            expect(state.anchorFitId == null || it.fits.any { fit -> fit.id == state.anchorFitId && fit.revision == state.saveSource?.fitRevision }, "anchor differs from bridge")
        }
        return OfflineImplantSetResponse(expected.requestId, true, committed, false, state, bridge, null).also { validateResult(it, expected) }
    }
    /** Also used by injected model transports so a typed success cannot bypass correlation/lifecycle checks. */
    fun validateResult(result: OfflineImplantSetResponse, request: OfflineImplantSetRequest, before: OfflineImplantSetState? = null) {
        expect(result.requestId == request.requestId, "result request identity differs")
        if (!result.ok) {
            expect(result.committed != true && (result.committed == null) == result.reopenRequired && result.state == null && result.bridge == null && result.error != null,
                "invalid failed result")
            expect((result.error?.code == "reopen_required") == result.reopenRequired, "failure reopen code differs")
            return
        }
        expect(result.committed != null && !result.reopenRequired && result.error == null && result.state != null, "invalid successful result")
        val after = checkNotNull(result.state)
        expect(after.context.sessionId == request.context.sessionId && after.context.datasetSha256 == request.context.datasetSha256 &&
            if (result.committed == true) request.context.generation < Long.MAX_VALUE && after.context.generation == request.context.generation + 1
            else after.context.generation == request.context.generation, "result context differs")
        expect(request.operation != "read" || result.committed == false && result.bridge == null, "read result mutated")
        if (request.operation != "read") expect(result.bridge != null && result.bridge.isSuccess && result.bridge.requestId == "bootstrap" &&
            result.bridge.sessionId == after.context.sessionId, "mutation result lacks complete bridge")
        val replay = request.operation in setOf("undo", "redo")
        expect(after.anchorFitId == request.anchorFitId || replay && after.anchorFitId == null, "result anchor differs")
        val disappeared = replay && request.anchorFitId != null && after.anchorFitId == null
        val target = if (disappeared && request.view.historyTarget != "library") "library" else request.view.historyTarget
        expect(after.view.query == request.view.query && after.view.offset == request.view.offset && after.view.limit == request.view.limit &&
            after.view.targetProfileId == request.view.targetProfileId && after.view.historyTarget == target && after.view.selectedSetId == selectionId(request, after.detail),
            "result view differs")
        expect(after.total >= 0 && after.entries.size.toLong() == minOf(request.view.limit.toLong(),
            if (after.total > request.view.offset) after.total - request.view.offset else 0), "result page incomplete")
        expect(if (after.anchorFitId == null) after.saveSource == null else after.saveSource?.fitId == after.anchorFitId, "result applied source anchor differs")
        if (request.view.targetProfileId != null) expect(after.destination == null || after.destination is OfflineImplantSetDestination.Profile &&
            after.destination.profileId == request.view.targetProfileId, "result character preview differs")
        else expect(if (after.anchorFitId == null) after.destination == null else after.destination is OfflineImplantSetDestination.Fit &&
            after.destination.fitId == after.anchorFitId, "result fit preview differs")
        validateSelection(after, request)
        val args = OfflineFeatureCodec.parse(request.argumentsJson)
        if (request.operation in setOf("create", "duplicate", "delete", "remove_item", "save_current")) expect(result.committed == true, "effective template change reported no-op")
        val old = before?.takeIf { it.context == request.context }
        if (request.operation in setOf("create", "duplicate", "save_current")) {
            expect(old == null || after.detail!!.entry.id !in old.entries.map { it.id } && after.detail.entry.id != old.detail?.entry?.id, "fresh identity reused a known set")
        }
        val previous = old?.detail?.takeIf { it.entry.id == request.view.selectedSetId }
        val current = after.detail
        if (previous != null && request.operation in setOperations) {
            expect(integer(args.get("revision")) == previous.entry.revision, "submitted set revision differs from captured detail")
            when (request.operation) {
                "duplicate" -> expect(current?.items == previous.items, "duplicate recipe contents differ")
                "apply_fit", "apply_profile" -> {
                    expect(current == previous, "application modified the recipe")
                    if (previous.items.isEmpty()) expect(result.committed == false, "empty application committed")
                    if (request.operation == "apply_profile" && previous.items.isNotEmpty()) expect(result.committed == true, "character recreation reported no-op")
                }
                "rename", "add_item", "remove_item" -> {
                    expect(current != null, "missing edited recipe")
                    val next = checkNotNull(current)
                    expect(next.entry.kind == previous.entry.kind && next.entry.family == previous.entry.family && next.entry.grade == previous.entry.grade,
                        "template metadata authority changed")
                    expect(if (result.committed == true) next.entry.revision > previous.entry.revision else next.entry.revision == previous.entry.revision, "set revision did not match effect")
                    when (request.operation) {
                        "rename" -> {
                            val label = text(args.get("name"))
                            expect(next.items == previous.items && next.entry.name == label && result.committed == (label != previous.entry.name), "rename result differs")
                        }
                        "remove_item" -> {
                            val id = itemId(args.get("item_id"))
                            expect(previous.items.any { it.itemId == id } && next.entry.name == previous.entry.name && next.items == previous.items.filterNot { it.itemId == id }, "remove result differs")
                        }
                        "add_item" -> {
                            val id = itemId(args.get("item_id")); val incoming = next.items.singleOrNull { it.itemId == id }
                            expect(incoming != null, "added implant absent")
                            val occupant = previous.items.singleOrNull { it.slot == incoming!!.slot }
                            val expectedOccupant = if (args.get("replace_item_id") === JSONObject.NULL) null else itemId(args.get("replace_item_id"))
                            expect(occupant?.itemId == expectedOccupant, "replacement occupant differs")
                            val expectedItems = previous.items.filterNot { it.slot == incoming!!.slot } + checkNotNull(incoming)
                            expect(next.entry.name == previous.entry.name && next.items == expectedItems && result.committed == (expectedItems != previous.items), "ordered add result differs")
                        }
                    }
                }
            }
        }
        if (old != null && result.committed == false) {
            if (request.view.historyTarget == old.view.historyTarget) expect(after.history == old.history, "no-op changed history")
            if (request.anchorFitId == old.anchorFitId) expect(after.saveSource == old.saveSource, "no-op changed applied source")
            if (request.anchorFitId == old.anchorFitId && request.view.targetProfileId == old.view.targetProfileId) expect(after.destination == old.destination, "no-op changed destination")
        }
    }

    /** Complete same-generation authority check; FitSnapshot.implants is LOCAL even under CHARACTER. */
    fun validateAuthority(state: OfflineImplantSetState, features: OfflineFeatureState, fits: List<FitSnapshot>, catalogue: CharacterImplantCatalog) {
        expect(state.context == features.context, "feature context differs")
        OfflineFeatureCodec.validateFits(features, fits); catalogue.validate(features)
        fun item(id: Int, name: String, slot: Int) {
            val actual = catalogue.itemById[id]
            expect(actual != null && actual.name == name && actual.slot == slot, "recipe or destination metadata differs from catalogue")
        }
        state.detail?.items?.forEach { item(it.itemId, it.name, it.slot) }
        state.destination?.implants?.forEach { item(it.itemId, it.name, it.slot) }
        val anchor = state.anchorFitId?.let { id -> fits.singleOrNull { it.id == id }.also { expect(it != null, "missing anchor fit") } }
        val profileTarget = state.view.targetProfileId
        if (profileTarget != null) {
            val profile = features.profiles.find { it.id == profileTarget }
            if (profile == null) expect(state.destination == null, "missing profile was retargeted")
            else {
                val target = state.destination as? OfflineImplantSetDestination.Profile
                expect(target != null && target.profileId == profile.id && target.profileRevision == profile.revision && target.name == profile.name && target.readonly == profile.readonly &&
                    target.assignedFitCount == features.bindings.values.count { it.profileId == profile.id }.toLong(), "profile summary differs")
                expect(target?.implants == profile.implants.map { OfflineImplantCollectionRow(it.implantId, it.itemId, it.name, it.slot, it.active) }, "profile collection differs")
            }
        } else if (anchor == null) expect(state.destination == null, "destination without anchor")
        else {
            val target = state.destination as? OfflineImplantSetDestination.Fit
            expect(target != null && target.fitId == anchor.id && target.fitRevision == anchor.revision && target.name == anchor.name, "fit summary differs")
            expect(target?.implants?.map { ImplantSnapshot(it.name, it.slot, it.active) } == anchor.implants, "local fit collection count/order/state differs")
        }
        if (anchor == null) expect(state.saveSource == null, "save source without anchor")
        else {
            val source = state.saveSource; val binding = features.bindings.getValue(anchor.id)
            expect(source != null && source.fitId == anchor.id && source.fitRevision == anchor.revision && source.source == binding.implantSource, "save source binding differs")
            if (binding.implantSource == ImplantLocation.FIT) {
                expect(source?.profileId == null && source?.profileRevision == null && source?.profileName == null && source?.implantCount == anchor.implants.size.toLong(),
                    "local save-source count/profile differs")
            } else {
                val actual = features.profiles.single { it.id == binding.profileId }
                expect(source != null && source.profileId == actual.id && source.profileRevision == actual.revision && source.profileName == actual.name && source.implantCount == actual.implants.size.toLong(),
                    "character save-source summary differs")
            }
        }
    }

    /** Validate meanings before publication, never by re-sending a mutation or invoking feature reads with side effects. */
    fun validateTransition(result: OfflineImplantSetResponse, request: OfflineImplantSetRequest, beforeState: OfflineImplantSetState?,
        beforeFeatures: OfflineFeatureState, beforeFits: List<FitSnapshot>, afterFeatures: OfflineFeatureState, catalogue: CharacterImplantCatalog) {
        expect(result.ok && request.operation != "read" && beforeFeatures.context == request.context, "mutation before-context differs")
        val state = checkNotNull(result.state); val fits = checkNotNull(result.bridge).fits
        validateResult(result, request, beforeState)
        validateAuthority(state, afterFeatures, fits, catalogue)
        if (result.committed == false) {
            expect(fits == beforeFits && afterFeatures.context == beforeFeatures.context && afterFeatures.profiles == beforeFeatures.profiles &&
                afterFeatures.bindings == beforeFeatures.bindings && afterFeatures.skills == beforeFeatures.skills, "no-op changed complete authority")
            if (afterFeatures.selectedFitId == beforeFeatures.selectedFitId) expect(afterFeatures.history == beforeFeatures.history, "no-op changed selected feature history")
        }
        val operation = request.operation; val args = OfflineFeatureCodec.parse(request.argumentsJson)
        if (operation in libraryOperations) {
            expect(fits == beforeFits && afterFeatures.profiles == beforeFeatures.profiles && afterFeatures.bindings == beforeFeatures.bindings && afterFeatures.skills == beforeFeatures.skills,
                "template operation changed fit or character authority")
            if (beforeFeatures.selectedFitId != null && afterFeatures.selectedFitId == beforeFeatures.selectedFitId)
                expect(afterFeatures.history == beforeFeatures.history, "template operation changed incidental fit history")
        }
        if (operation == "save_current") {
            val fit = beforeFits.single { it.id == request.anchorFitId }; val binding = beforeFeatures.bindings.getValue(fit.id)
            expect(integer(args.get("fit_revision"), 1) == fit.revision, "save source revision differs")
            val ids = if (binding.implantSource == ImplantLocation.CHARACTER) beforeFeatures.profiles.single { it.id == binding.profileId }.implants.map { it.itemId }
                else fit.implants.map { row -> catalogue.items.singleOrNull { it.name == row.name && it.slot == row.slot }?.itemId
                    ?: OfflineFeatureCodec.reject("Implant sets: local save item cannot be resolved uniquely") }
            expect(ids.isNotEmpty() && state.detail?.items?.map { it.itemId } == ids, "save-current recipe differs from actually applied collection")
        }
        if (operation in setOf("apply_fit", "apply_profile")) {
            val previous = beforeState?.takeIf { it.context == request.context }?.detail
            expect(previous != null && previous.entry.id == request.view.selectedSetId, "application lacks captured verified recipe")
            val recipe = checkNotNull(previous)
            expect(afterFeatures.skills == beforeFeatures.skills && afterFeatures.bindings.keys == beforeFeatures.bindings.keys, "application changed unrelated authority")
            afterFeatures.bindings.forEach { (id, value) ->
                val old = beforeFeatures.bindings.getValue(id)
                expect(value.profileId == old.profileId && value.implantSource == old.implantSource, "application switched profile or implant source")
            }
            if (operation == "apply_fit") {
                expect(afterFeatures.profiles == beforeFeatures.profiles, "local application modified characters")
                val old = beforeState?.destination as? OfflineImplantSetDestination.Fit
                val next = state.destination as? OfflineImplantSetDestination.Fit
                expect(old != null && next != null && !old.isStructure && !next.isStructure && old.fitId == request.anchorFitId &&
                    integer(args.get("fit_revision"), 1) == old.fitRevision, "fit application target differs")
                validateMerge(checkNotNull(old).implants, checkNotNull(next).implants, recipe.items, false)
                val changed = recipe.items.any { incoming -> old.implants.none { it.itemId == incoming.itemId } }
                expect(result.committed == changed, "fit duplicate-only effect differs")
                expect(if (changed) next.fitRevision > old.fitRevision else next.fitRevision == old.fitRevision, "fit application revision differs")
            } else {
                val id = profile(args.get("profile_id")); val old = beforeFeatures.profiles.single { it.id == id }; val next = afterFeatures.profiles.single { it.id == id }
                expect(!old.readonly && integer(args.get("profile_revision"), 1) == old.revision && old.copy(revision = next.revision, implants = next.implants) == next,
                    "character application changed skills/name or target")
                expect(beforeFeatures.profiles.filterNot { it.id == id } == afterFeatures.profiles.filterNot { it.id == id }, "application changed another profile")
                expect(if (recipe.items.isEmpty()) next.revision == old.revision else next.revision > old.revision, "character application revision differs")
                fun rows(profile: OfflineProfile) = profile.implants.map { OfflineImplantCollectionRow(it.implantId, it.itemId, it.name, it.slot, it.active) }
                validateMerge(rows(old), rows(next), recipe.items, true)
            }
        }
    }
    private fun validateMerge(before: List<OfflineImplantCollectionRow>, after: List<OfflineImplantCollectionRow>, recipe: List<OfflineImplantSetItem>, recreate: Boolean) {
        val expected = before.toMutableList(); val freshSlots = mutableSetOf<Int>()
        for (item in recipe) {
            if (!recreate && expected.any { it.itemId == item.itemId }) continue
            expected.removeAll { it.slot == item.slot }
            expected += OfflineImplantCollectionRow("", item.itemId, item.name, item.slot, true)
            freshSlots += item.slot
        }
        expect(after.size == expected.size, "application collection count differs")
        val oldIds = before.map { it.rowId }.toSet()
        after.zip(expected).forEach { (actual, wanted) ->
            if (wanted.slot in freshSlots) expect(actual.copy(rowId = "") == wanted && actual.rowId !in oldIds, "application did not create a fresh active row")
            else expect(actual == wanted, "application changed retained or skipped row")
        }
    }
}
