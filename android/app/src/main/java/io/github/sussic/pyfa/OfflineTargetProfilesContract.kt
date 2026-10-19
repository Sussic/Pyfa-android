package io.github.sussic.pyfa

import org.json.JSONObject

/** Target-only v1. Raw Long/Double kinds and signed zero are never rewritten by reads. */
internal val TARGET_FIELDS = listOf("emAmount", "thermalAmount", "kineticAmount", "explosiveAmount", "maxVelocity", "signatureRadius", "radius", "hp")
internal val TARGET_LABELS = listOf("EM resistance (%)", "Thermal resistance (%)", "Kinetic resistance (%)", "Explosive resistance (%)", "Maximum velocity (m/s)", "Signature radius (m)", "Physical radius (m)", "HP")
data class OfflineTargetValues(val fields: Map<String, Number?>) {
    fun json(): JSONObject = JSONObject().also { row -> TARGET_FIELDS.forEach { row.put(it, fields[it] ?: JSONObject.NULL) } }
}
data class OfflineTargetEntry(val id: String, val kind: String, val name: String, val revision: Long, val boundFitCount: Long) {
    val readonly get() = kind == "builtin"
}
data class OfflineTargetBoundFit(val id: String, val name: String, val revision: Long)
data class OfflineTargetDetail(val entry: OfflineTargetEntry, val values: OfflineTargetValues, val effective: OfflineTargetValues,
    val boundOffset: Long, val boundFits: List<OfflineTargetBoundFit>)
data class OfflineTargetSelection(val kind: String, val targetId: String?, val bindingRevision: Long?)
data class OfflineTargetView(val query: String = "", val offset: Long = 0, val limit: Int = 50,
    val selectedTargetId: String? = null, val boundOffset: Long = 0) {
    fun json(): JSONObject = JSONObject().put("query", query).put("offset", offset).put("limit", limit)
        .put("selected_target_id", selectedTargetId ?: JSONObject.NULL).put("bound_offset", boundOffset)
}
data class OfflineTargetState(val context: OfflineContext, val fitId: String?, val fitRevision: Long?,
    val selection: OfflineTargetSelection, val view: OfflineTargetView, val total: Long, val entries: List<OfflineTargetEntry>,
    val detail: OfflineTargetDetail?, val history: OfflineHistory)
data class OfflineTargetRequest(val requestId: String, val context: OfflineContext, val fitId: String?,
    val view: OfflineTargetView = OfflineTargetView(), val operation: String = "read", val argumentsJson: String = "{}") {
    fun json(): String = OfflineTargetCodec.request(this)
}
data class OfflineTargetResponse(val requestId: String, val ok: Boolean, val committed: Boolean?, val reopenRequired: Boolean,
    val state: OfflineTargetState?, val bridge: BridgeResponse?, val error: OfflineFeatureError?)

internal object OfflineTargetCodec {
    private fun expect(test: Boolean, message: String) = OfflineFeatureCodec.expect(test, "Targets: $message")
    private fun obj(raw: Any) = OfflineFeatureCodec.obj(raw)
    private fun keys(row: JSONObject, vararg names: String) = OfflineFeatureCodec.keys(row, *names)
    private fun text(raw: Any) = OfflineFeatureCodec.text(raw)
    private fun integer(raw: Any, minimum: Long = 0): Long = OfflineFeatureCodec.integer(raw).also { expect(it >= minimum, "invalid count/revision") }
    private fun nullableText(raw: Any) = OfflineFeatureCodec.nullableText(raw)
    private fun nullableLong(raw: Any) = if (raw === JSONObject.NULL) null else integer(raw, 1)
    private fun fitId(raw: Any) = text(raw).also { expect(it.matches(Regex("[0-9a-f]{32}")), "invalid fit ID") }
    fun targetId(raw: Any): String = text(raw).also {
        expect(it.matches(Regex("target:[0-9a-f]{32}")) || it.startsWith("target:builtin:") &&
            it.removePrefix("target:builtin:").toIntOrNull()?.let { n -> n in -195..-1 && it == "target:builtin:$n" } == true, "invalid target ID")
    }
    private fun context(raw: Any): OfflineContext = OfflineFeatureCodec.context(obj(raw)).also {
        expect(it.sessionId.matches(Regex("[0-9a-f]{32}")), "invalid session")
    }
    // Python str.strip whitespace, including NBSP and U+001C..U+001F; not Java trim's wider <=32 set.
    private fun space(c: Char) = c in '\u0009'..'\u000D' || c in '\u001C'..'\u0020' || c == '\u0085' || c == '\u00A0' ||
        c == '\u1680' || c in '\u2000'..'\u200A' || c == '\u2028' || c == '\u2029' || c == '\u202F' || c == '\u205F' || c == '\u3000'
    fun cleanText(raw: Any, allowEmpty: Boolean = false): String = text(raw).also { value ->
        expect(value.codePointCount(0, value.length) <= 200 && (allowEmpty || value.isNotEmpty()) &&
            value.none { Character.getType(it) == Character.CONTROL.toInt() }, "use up to 200 Unicode characters without controls")
    }
    fun name(raw: String): String = cleanText(raw.trim(::space))
    private fun revision(id: String, raw: Any) = integer(raw).also {
        expect(if (id.startsWith("target:builtin:")) it == 0L else it >= 1, "invalid target revision")
    }
    fun values(raw: Any, editor: Boolean = false): OfflineTargetValues {
        val row = obj(raw); keys(row, *TARGET_FIELDS.toTypedArray())
        val values = TARGET_FIELDS.mapIndexed { index, key ->
            val value = row.get(key)
            val number = if (value === JSONObject.NULL) { expect(index >= 4, "resistance cannot be null"); null }
            else {
                expect(value is Long || value is Int || value is Double, "finite number required")
                expect(!editor || value is Double, "editor values require decimal tokens")
                (value as Number).also {
                    val n = it.toDouble(); expect(n.isFinite() && n >= 0 && (index >= 4 || n <= 1), "target value outside supported domain")
                }
            }
            key to number
        }.toMap()
        return OfflineTargetValues(OfflineFeatureCodec.frozen(values))
    }
    private fun same(a: Number?, b: Number?): Boolean = when {
        a == null || b == null -> a == null && b == null
        a is Double && b is Double -> a.toBits() == b.toBits()
        a is Double || b is Double -> false
        else -> a.toLong() == b.toLong()
    }
    private fun entry(row: JSONObject, detail: Boolean = false): OfflineTargetEntry {
        val metadata = arrayOf("target_id", "kind", "name", "revision", "bound_fit_count")
        keys(row, *(if (detail) metadata + arrayOf("values", "effective", "bound_fits") else metadata))
        val id = targetId(row.get("target_id")); val kind = text(row.get("kind"))
        expect(kind == if (id.startsWith("target:builtin:")) "builtin" else "custom", "target kind differs")
        val label = cleanText(row.get("name")); if (kind == "custom") expect(label == name(label), "untrimmed name")
        return OfflineTargetEntry(id, kind, label, revision(id, row.get("revision")), integer(row.get("bound_fit_count")))
    }
    private fun pageSize(count: Int, offset: Long, limit: Int, total: Long) {
        expect(count <= limit && count.toLong() == minOf(limit.toLong(), (total - offset).coerceAtLeast(0)), "incomplete page")
    }
    private fun history(raw: Any): OfflineHistory {
        val row = obj(raw); keys(row, "undo_count", "redo_count", "limit", "undo_label", "redo_label")
        val undo = integer(row.get("undo_count")); val redo = integer(row.get("redo_count"))
        expect(integer(row.get("limit")) == 100L && undo <= 100 && redo <= 100 && undo + redo <= 100, "invalid history")
        fun label(key: String, count: Long) = nullableText(row.get(key)).also { expect(if (count == 0L) it == null else !it.isNullOrBlank(), "history label differs") }
        return OfflineHistory(undo.toInt(), redo.toInt(), 100, label("undo_label", undo), label("redo_label", redo))
    }
    private fun validateView(value: OfflineTargetView) {
        cleanText(value.query, true); expect(value.offset >= 0 && value.boundOffset >= 0 && value.limit in 1..50, "invalid page")
        value.selectedTargetId?.let(::targetId)
    }
    fun request(value: OfflineTargetRequest): String {
        expect(value.requestId.length in 1..128 && value.requestId.all { it.code in 32..126 }, "invalid request ID")
        context(value.context.json()); value.fitId?.let(::fitId); validateView(value.view)
        val args = OfflineFeatureCodec.parse(value.argumentsJson)
        fun target() { val id = targetId(args.get("target_id")); revision(id, args.get("revision")) }
        fun custom() { target(); expect(!args.getString("target_id").startsWith("target:builtin:"), "built-in is read-only") }
        fun named() { expect(name(text(args.get("name"))) == text(args.get("name")), "untrimmed name") }
        fun fit() { expect(value.fitId != null, "fit required"); integer(args.get("fit_revision"), 1) }
        when (value.operation) {
            "read", "undo", "redo" -> keys(args)
            "create" -> { keys(args, "name", "values"); named(); values(args.get("values"), true) }
            "update_values" -> { keys(args, "target_id", "revision", "values"); custom(); values(args.get("values"), true) }
            "rename" -> { keys(args, "target_id", "revision", "name"); custom(); named() }
            "duplicate" -> { keys(args, "target_id", "revision", "name"); target(); named() }
            "assign" -> { keys(args, "target_id", "revision", "fit_revision"); target(); fit() }
            "clear" -> { keys(args, "fit_revision"); fit() }
            "delete" -> { keys(args, "target_id", "revision", "bound_fit_count"); custom(); integer(args.get("bound_fit_count")) }
            else -> expect(false, "unknown operation")
        }
        return OfflineFeatureCodec.json(JSONObject().put("version", 1).put("request_id", value.requestId).put("context", value.context.json())
            .put("fit_id", value.fitId ?: JSONObject.NULL).put("view", value.view.json()).put("operation", value.operation).put("arguments", args))
            .also { expect(it.toByteArray(Charsets.UTF_8).size <= 16_384, "request exceeds byte limit") }
    }
    private fun state(root: JSONObject, expected: OfflineTargetRequest): OfflineTargetState {
        keys(root, "version", "context", "fit_id", "fit_revision", "selection", "page", "detail", "history")
        expect(integer(root.get("version")) == 1L, "unsupported state version")
        val context = context(root.get("context"))
        expect(context.sessionId == expected.context.sessionId && context.datasetSha256 == expected.context.datasetSha256 &&
            context.generation >= expected.context.generation, "response context differs")
        val fit = nullableText(root.get("fit_id"))?.let(::fitId); val revision = nullableLong(root.get("fit_revision"))
        expect((fit == null) == (revision == null) && (fit == expected.fitId || fit == null && expected.operation in setOf("undo", "redo")), "fit differs")
        val selection = obj(root.get("selection")); keys(selection, "kind", "target_id", "binding_revision")
        val kind = text(selection.get("kind")); val selectedId = nullableText(selection.get("target_id"))?.let(::targetId)
        val bindingRevision = nullableLong(selection.get("binding_revision"))
        expect(kind in setOf("no_fit", "none", "anonymous", "named") && (kind == "no_fit") == (fit == null), "invalid selection")
        expect((kind == "named") == (selectedId != null) && (kind == "named") == (bindingRevision != null), "invalid binding")
        val page = obj(root.get("page")); keys(page, "query", "offset", "limit", "total", "entries")
        expect(cleanText(page.get("query"), true) == expected.view.query && integer(page.get("offset")) == expected.view.offset &&
            integer(page.get("limit")) == expected.view.limit.toLong(), "page differs")
        val total = integer(page.get("total")); val entries = OfflineFeatureCodec.rows(page.get("entries")).map { entry(obj(it)) }
        pageSize(entries.size, expected.view.offset, expected.view.limit, total)
        expect(entries.map { it.id }.distinct().size == entries.size, "duplicate page target")
        val detail = if (root.get("detail") === JSONObject.NULL) null else obj(root.get("detail")).let { row ->
            val metadata = entry(row, true); val raw = values(row.get("values")); val effective = values(row.get("effective"))
            for (key in TARGET_FIELDS) {
                val original = raw.fields[key]
                val wanted: Number? = if (key in setOf("maxVelocity", "radius") && (original == null || original.toDouble() == 0.0)) 0L else original
                expect(same(wanted, effective.fields[key]), "effective projection differs for $key")
            }
            val bound = obj(row.get("bound_fits")); keys(bound, "offset", "limit", "total", "entries")
            expect(integer(bound.get("offset")) == expected.view.boundOffset && integer(bound.get("limit")) == 50L &&
                integer(bound.get("total")) == metadata.boundFitCount, "bound-fit page differs")
            val fits = OfflineFeatureCodec.rows(bound.get("entries")).map { obj(it).let { item ->
                keys(item, "fit_id", "name", "revision")
                OfflineTargetBoundFit(fitId(item.get("fit_id")), (item.get("name") as? String ?: OfflineFeatureCodec.reject("Targets: fit name must be text")).also { expect(it.isNotEmpty(), "empty fit name") }, integer(item.get("revision"), 1))
            } }
            pageSize(fits.size, expected.view.boundOffset, 50, metadata.boundFitCount)
            expect(fits.map { it.id }.distinct().size == fits.size, "duplicate bound fit")
            entries.find { it.id == metadata.id }?.let { expect(it == metadata, "detail metadata differs") }
            OfflineTargetDetail(metadata, raw, effective, expected.view.boundOffset, OfflineFeatureCodec.frozen(fits))
        }
        if (kind == "named") {
            entries.find { it.id == selectedId }?.let { expect(it.boundFitCount > 0, "named selection has no binding") }
            detail?.let { if (it.entry.id == selectedId) expect(it.entry.boundFitCount > 0, "named detail has no binding") }
        }
        detail?.let { currentDetail -> currentDetail.boundFits.find { it.id == fit }?.let {
            expect(kind == "named" && selectedId == currentDetail.entry.id && it.revision == revision, "selected bound fit differs")
        } }
        when (expected.operation) {
            "create", "duplicate" -> expect(detail != null && !detail.entry.readonly, "missing created detail")
            "delete" -> {
                val deleted = OfflineFeatureCodec.parse(expected.argumentsJson).getString("target_id")
                expect(detail?.entry?.id == expected.view.selectedTargetId?.takeIf { it != deleted }, "deleted detail differs")
            }
            "undo", "redo" -> expect(detail == null || detail.entry.id == expected.view.selectedTargetId, "detail selection differs")
            else -> expect(detail?.entry?.id == expected.view.selectedTargetId, "detail selection differs")
        }
        return OfflineTargetState(context, fit, revision, OfflineTargetSelection(kind, selectedId, bindingRevision), expected.view.copy(selectedTargetId = detail?.entry?.id),
            total, OfflineFeatureCodec.frozen(entries), detail, history(root.get("history")))
    }
    /** Count the original state wire bytes, including escaped astral characters, not a re-encoded approximation. */
    private fun stateByteCount(raw: String): Int {
        var position = 0
        fun whitespace() { while (position < raw.length && raw[position].isWhitespace()) position++ }
        fun stringEnd(): Int {
            position++
            while (position < raw.length) {
                when (raw[position++]) {
                    '\\' -> position++
                    '"' -> return position
                }
            }
            return position
        }
        whitespace(); position++
        while (position < raw.length) {
            whitespace(); val keyStart = position; val keyEnd = stringEnd()
            val key = StrictJson(raw.substring(keyStart, keyEnd)).parse()
            whitespace(); position++; whitespace(); val start = position
            var depth = 0
            while (position < raw.length) {
                val c = raw[position]
                if (c == '"') { stringEnd(); continue }
                if (c == '{' || c == '[') depth++
                if (c == '}' || c == ']') { if (depth == 0) break; depth-- }
                if (c == ',' && depth == 0) break
                position++
            }
            if (key == "state") return raw.substring(start, position).trimEnd().toByteArray(Charsets.UTF_8).size
            if (position < raw.length && raw[position] == ',') position++ else break
        }
        throw BridgeProtocolException("Targets: absent state")
    }
    fun response(raw: String, expected: OfflineTargetRequest): OfflineTargetResponse {
        val row = OfflineFeatureCodec.parse(raw)
        keys(row, "version", "request_id", "ok", "committed", "reopen_required", "state", "bridge", "error")
        expect(integer(row.get("version")) == 1L && text(row.get("request_id")) == expected.requestId, "response identity differs")
        val ok = OfflineFeatureCodec.bool(row.get("ok")); val reopen = OfflineFeatureCodec.bool(row.get("reopen_required"))
        val committed = row.get("committed").let { if (it === JSONObject.NULL) null else OfflineFeatureCodec.bool(it) }
        if (!ok) {
            expect(committed != true && (committed == null) == reopen && row.get("state") === JSONObject.NULL && row.get("bridge") === JSONObject.NULL, "partial/ambiguous failure")
            val error = obj(row.get("error")); keys(error, "code", "message")
            return OfflineTargetResponse(expected.requestId, false, committed, reopen, null, null,
                OfflineFeatureError(text(error.get("code")), text(error.get("message")).also { expect(it.isNotEmpty() && it.codePointCount(0, it.length) <= 1024 && it.none { c -> Character.getType(c) == Character.CONTROL.toInt() }, "invalid error text") }))
        }
        expect(committed != null && !reopen && row.get("error") === JSONObject.NULL, "ambiguous success")
        expect(stateByteCount(raw) <= 524_288, "state exceeds byte limit")
        val state = state(obj(row.get("state")), expected)
        expect(state.context.generation == if (committed == true) Math.addExact(expected.context.generation, 1) else expected.context.generation, "generation differs")
        val bridge = if (expected.operation == "read") {
            expect(committed == false && row.get("bridge") === JSONObject.NULL && state.context == expected.context, "read mutated state"); null
        } else {
            if (committed == false) expect(state.context == expected.context, "no-op changed context")
            BridgeCodec.decodeResponse(OfflineFeatureCodec.json(row.get("bridge"))).also {
                expect(it.isSuccess && it.requestId == "bootstrap" && it.sessionId == state.context.sessionId, "invalid committed bridge")
                expect(state.fitId == null || it.fits.any { fit -> fit.id == state.fitId && fit.revision == state.fitRevision }, "selected bridge fit differs")
                state.detail?.boundFits?.forEach { bound -> expect(it.fits.any { fit -> fit.id == bound.id && fit.revision == bound.revision && fit.name == bound.name }, "bound bridge fit differs") }
            }
        }
        return OfflineTargetResponse(expected.requestId, true, committed, false, state, bridge, null)
    }
}
