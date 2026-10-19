package io.github.sussic.pyfa

import org.json.JSONObject

/** Damage-only v3. Raw Long/Double kinds and signed zero are never rewritten by reads. */
internal const val SELECTED_AMMO_PATTERN_ID = "damage:selected_ammo"
internal fun damageReadLike(operation: String) = operation in setOf("read", "item_options", "module_options")
internal val DAMAGE_PATTERN_FIELDS = listOf("emAmount", "thermalAmount", "kineticAmount", "explosiveAmount")
internal val DAMAGE_PATTERN_LABELS = listOf("EM contribution", "Thermal contribution", "Kinetic contribution", "Explosive contribution")
data class OfflineDamageValues(val fields: Map<String, Number>) {
    fun json(): JSONObject = JSONObject().also { row -> DAMAGE_PATTERN_FIELDS.forEach { row.put(it, fields.getValue(it)) } }
}
data class OfflineDamageEntry(val id: String, val kind: String, val name: String, val revision: Long, val boundFitCount: Long, val assignable: Boolean, val unassignableReason: String?,
    val boundModuleCount: Long = 0, val affectedFitCount: Long = boundFitCount) {
    val readonly get() = kind != "custom"
    val duplicable get() = kind != "selected_ammo"
}
data class OfflineDamageItem(val itemId: Int, val name: String, val eligible: Boolean, val available: Boolean,
    val unavailableReason: String?, val values: OfflineDamageValues?)
data class OfflineDamageBoundFit(val id: String, val name: String, val revision: Long)
data class OfflineDamageBoundModule(val fitId: String, val fitName: String, val fitRevision: Long,
    val objectKey: String, val position: Int, val itemId: Int, val name: String)
data class OfflineDamageDetail(val entry: OfflineDamageEntry, val values: OfflineDamageValues, val percentages: OfflineDamageValues,
    val boundOffset: Long, val boundFits: List<OfflineDamageBoundFit>,
    val moduleOffset: Long = 0, val boundModules: List<OfflineDamageBoundModule> = emptyList())
data class OfflineDamageSelection(val kind: String, val patternId: String?, val patternRevision: Long?, val bindingRevision: Long?)
data class OfflineDamageView(val query: String = "", val offset: Long = 0, val limit: Int = 50,
    val selectedPatternId: String? = null, val boundOffset: Long = 0, val moduleOffset: Long = 0) {
    fun json(): JSONObject = JSONObject().put("query", query).put("offset", offset).put("limit", limit)
        .put("selected_pattern_id", selectedPatternId ?: JSONObject.NULL).put("bound_offset", boundOffset).put("module_offset", moduleOffset)
}
data class OfflineDamageState(val context: OfflineContext, val fitId: String?, val fitRevision: Long?,
    val selection: OfflineDamageSelection, val view: OfflineDamageView, val total: Long, val entries: List<OfflineDamageEntry>,
    val detail: OfflineDamageDetail?, val history: OfflineHistory, val item: OfflineDamageItem? = null, val module: ModuleRahRow? = null)
data class OfflineDamageRequest(val requestId: String, val context: OfflineContext, val fitId: String?,
    val view: OfflineDamageView = OfflineDamageView(), val operation: String = "read", val argumentsJson: String = "{}") {
    fun json(): String = OfflineDamageCodec.request(this)
}
data class OfflineDamageResponse(val requestId: String, val ok: Boolean, val committed: Boolean?, val reopenRequired: Boolean,
    val state: OfflineDamageState?, val bridge: BridgeResponse?, val error: OfflineFeatureError?)

internal object OfflineDamageCodec {
    private fun expect(test: Boolean, message: String) = OfflineFeatureCodec.expect(test, "Damage patterns: $message")
    private fun obj(raw: Any) = OfflineFeatureCodec.obj(raw)
    private fun keys(row: JSONObject, vararg names: String) = OfflineFeatureCodec.keys(row, *names)
    private fun text(raw: Any) = OfflineFeatureCodec.text(raw)
    private fun integer(raw: Any, minimum: Long = 0): Long = OfflineFeatureCodec.integer(raw).also { expect(it >= minimum, "invalid count/revision") }
    private fun nullableText(raw: Any) = OfflineFeatureCodec.nullableText(raw)
    private fun nullableLong(raw: Any) = if (raw === JSONObject.NULL) null else integer(raw, 1)
    private fun fitId(raw: Any) = text(raw).also { expect(it.matches(Regex("[0-9a-f]{32}")), "invalid fit ID") }
    fun patternId(raw: Any): String = text(raw).also {
        expect(it == SELECTED_AMMO_PATTERN_ID || it.matches(Regex("damage:[0-9a-f]{32}")) || it.startsWith("damage:builtin:") &&
            it.removePrefix("damage:builtin:").toIntOrNull()?.let { n -> n in -118..-1 && it == "damage:builtin:$n" } == true, "invalid pattern ID")
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
    fun name(raw: String): String = cleanText(raw.trim(::space)).also {
        expect(it !in setOf("Uniform", "Selected Ammo"), "this name is reserved")
    }
    private fun revision(id: String, raw: Any) = integer(raw).also {
        expect(if (id.startsWith("damage:builtin:")) it == 0L else it >= 1, "invalid pattern revision")
    }
    fun values(raw: Any, editor: Boolean = false): OfflineDamageValues {
        val row = obj(raw); keys(row, *DAMAGE_PATTERN_FIELDS.toTypedArray())
        val fields = DAMAGE_PATTERN_FIELDS.associateWith { key ->
            val value = row.get(key)
            expect(value is Long || value is Int || value is Double, "finite number required")
            expect(!editor || value is Double, "editor values require decimal tokens")
            (value as Number).also { expect(it.toDouble().isFinite() && it.toDouble() >= 0, "negative or nonfinite contribution") }
        }
        return OfflineDamageValues(OfflineFeatureCodec.frozen(fields)).also { total(it) }
    }
    /** Match Python's fixed-order integer accumulation until the first float. */
    fun total(values: OfflineDamageValues): Double {
        var integer = java.math.BigInteger.ZERO
        var floating: Double? = null
        for (key in DAMAGE_PATTERN_FIELDS) {
            val value = values.fields.getValue(key)
            if (floating != null) floating += value.toDouble()
            else if (value is Double) floating = integer.toDouble() + value
            else integer += java.math.BigInteger.valueOf(value.toLong())
        }
        return (floating ?: integer.toDouble()).also { expect(it.isFinite(), "overflowing contribution total") }
    }
    private fun percentages(raw: Any, values: OfflineDamageValues): OfflineDamageValues {
        val row = obj(raw); keys(row, *DAMAGE_PATTERN_FIELDS.toTypedArray())
        val total = total(values)
        return OfflineDamageValues(OfflineFeatureCodec.frozen(DAMAGE_PATTERN_FIELDS.associateWith { key ->
            val value = row.get(key)
            expect(value is Double, "percentage must be a floating-point token")
            val number = value as Double
            val derived = if (total > 0) values.fields.getValue(key).toDouble() / total * 100.0 else 0.0
            expect(number.isFinite() && number in 0.0..100.0 && kotlin.math.abs(number - derived) <= 1e-9, "percentage differs")
            if (total == 0.0) expect(number.toBits() == 0.0.toBits(), "zero-total percentage must be positive zero")
            number
        }))
    }
    private fun entry(row: JSONObject, detail: Boolean = false): OfflineDamageEntry {
        val metadata = arrayOf("pattern_id", "kind", "name", "revision", "bound_fit_count", "bound_module_count", "affected_fit_count", "assignable", "unassignable_reason")
        keys(row, *(if (detail) metadata + arrayOf("values", "percentages", "bound_fits", "bound_modules") else metadata))
        val id = patternId(row.get("pattern_id")); val kind = text(row.get("kind"))
        expect(kind == when { id == SELECTED_AMMO_PATTERN_ID -> "selected_ammo"; id.startsWith("damage:builtin:") -> "builtin"; else -> "custom" }, "pattern kind differs")
        val label = cleanText(row.get("name")); if (kind == "custom") expect(label == name(label), "untrimmed name")
        if (kind == "selected_ammo") expect(label == "Selected Ammo", "protected pattern name differs")
        val count = integer(row.get("bound_fit_count"))
        val modules = integer(row.get("bound_module_count")); val affected = integer(row.get("affected_fit_count"))
        expect(affected >= count && affected - count <= modules && (modules == 0L || affected > 0), "inconsistent holder counts")
        expect(kind != "builtin" || modules == 0L && affected == count, "builtin module count is not a named holder")
        val assignable = OfflineFeatureCodec.bool(row.get("assignable"))
        val reason = nullableText(row.get("unassignable_reason"))
        expect(if (assignable) reason == null else reason == "zero_total" && kind == "custom" && count == 0L && modules == 0L && affected == 0L, "invalid assignability")
        return OfflineDamageEntry(id, kind, label, revision(id, row.get("revision")), count, assignable, reason, modules, affected)
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
    private fun validateView(value: OfflineDamageView) {
        cleanText(value.query, true); expect(value.offset >= 0 && value.boundOffset >= 0 && value.moduleOffset >= 0 && value.limit in 1..50, "invalid page")
        value.selectedPatternId?.let(::patternId)
    }
    fun request(value: OfflineDamageRequest): String {
        expect(value.requestId.length in 1..128 && value.requestId.all { it.code in 32..126 }, "invalid request ID")
        context(value.context.json()); value.fitId?.let(::fitId); validateView(value.view)
        val args = OfflineFeatureCodec.parse(value.argumentsJson)
        fun pattern() { val id = patternId(args.get("pattern_id")); revision(id, args.get("revision")) }
        fun custom() { pattern(); expect(args.getString("pattern_id").matches(Regex("damage:[0-9a-f]{32}")), "protected pattern is read-only") }
        fun named() { expect(name(text(args.get("name"))) == text(args.get("name")), "untrimmed name") }
        fun fit() { expect(value.fitId != null, "fit required"); integer(args.get("fit_revision"), 1) }
        when (value.operation) {
            "read", "undo", "redo" -> keys(args)
            "create" -> { keys(args, "name", "values"); named(); values(args.get("values"), true) }
            "update_values" -> { keys(args, "pattern_id", "revision", "values"); custom(); values(args.get("values"), true) }
            "rename" -> { keys(args, "pattern_id", "revision", "name"); custom(); named() }
            "duplicate" -> { keys(args, "pattern_id", "revision", "name"); pattern();
                expect(args.getString("pattern_id") != SELECTED_AMMO_PATTERN_ID, "Selected Ammo cannot be duplicated"); named() }
            "assign" -> { keys(args, "pattern_id", "revision", "fit_revision"); pattern(); fit() }
            "detach_to_anonymous" -> {
                keys(args, "pattern_id", "revision", "binding_revision", "fit_revision")
                pattern(); fit(); integer(args.get("binding_revision"), 1)
            }
            "reset_uniform" -> { keys(args, "fit_revision"); fit() }
            "item_options", "apply_item" -> {
                keys(args, "item_id", "fit_revision"); fit()
                expect(integer(args.get("item_id"), 1) <= Int.MAX_VALUE, "item ID exceeds Int32")
            }
            "module_options", "set_module" -> {
                keys(args, *(if (value.operation == "set_module") arrayOf("fit_revision", "object_key", "position", "selection")
                    else arrayOf("fit_revision", "object_key", "position")))
                fit(); fitId(args.get("object_key")); expect(integer(args.get("position")) <= Int.MAX_VALUE, "module position exceeds Int32")
                if (value.operation == "set_module") ModuleRahCodec.selection(args.get("selection"))
            }
            "delete" -> {
                keys(args, "pattern_id", "revision", "bound_fit_count", "bound_module_count", "affected_fit_count"); custom()
                val fits = integer(args.get("bound_fit_count")); val modules = integer(args.get("bound_module_count"))
                val affected = integer(args.get("affected_fit_count"))
                expect(affected >= fits && affected - fits <= modules && (modules == 0L || affected > 0), "invalid deletion impact")
            }
            else -> expect(false, "unknown operation")
        }
        return OfflineFeatureCodec.json(JSONObject().put("version", 3).put("request_id", value.requestId).put("context", value.context.json())
            .put("fit_id", value.fitId ?: JSONObject.NULL).put("view", value.view.json()).put("operation", value.operation).put("arguments", args))
            .also { expect(it.toByteArray(Charsets.UTF_8).size <= 16_384, "request exceeds byte limit") }
    }
    private fun state(root: JSONObject, expected: OfflineDamageRequest): OfflineDamageState {
        keys(root, "version", "context", "fit_id", "fit_revision", "selection", "page", "detail", "history", "item", "module")
        expect(integer(root.get("version")) == 3L, "unsupported state version")
        val context = context(root.get("context"))
        expect(context.sessionId == expected.context.sessionId && context.datasetSha256 == expected.context.datasetSha256 &&
            context.generation >= expected.context.generation, "response context differs")
        val fit = nullableText(root.get("fit_id"))?.let(::fitId); val revision = nullableLong(root.get("fit_revision"))
        expect((fit == null) == (revision == null) && (fit == expected.fitId || fit == null && expected.operation in setOf("undo", "redo")), "fit differs")
        val selection = obj(root.get("selection")); keys(selection, "kind", "pattern_id", "pattern_revision", "binding_revision")
        val kind = text(selection.get("kind")); val selectedId = nullableText(selection.get("pattern_id"))?.let(::patternId)
        val patternRevision = if (selection.get("pattern_revision") === JSONObject.NULL) null else {
            expect(selectedId != null, "revision without named pattern"); revision(checkNotNull(selectedId), selection.get("pattern_revision"))
        }
        val bindingRevision = nullableLong(selection.get("binding_revision"))
        expect(kind in setOf("no_fit", "anonymous", "named") && (kind == "no_fit") == (fit == null), "invalid selection")
        expect((kind == "named") == (selectedId != null) && (kind == "named") == (bindingRevision != null) && (kind == "named") == (patternRevision != null), "invalid binding")
        val page = obj(root.get("page")); keys(page, "query", "offset", "limit", "total", "entries")
        expect(cleanText(page.get("query"), true) == expected.view.query && integer(page.get("offset")) == expected.view.offset &&
            integer(page.get("limit")) == expected.view.limit.toLong(), "page differs")
        val total = integer(page.get("total")); val entries = OfflineFeatureCodec.rows(page.get("entries")).map { entry(obj(it)) }
        pageSize(entries.size, expected.view.offset, expected.view.limit, total)
        expect(entries.map { it.id }.distinct().size == entries.size, "duplicate page pattern")
        var section = 0; var lastBuiltin = 0
        for (entry in entries) {
            val next = when (entry.kind) { "builtin" -> 0; "selected_ammo" -> 1; else -> 2 }
            expect(next >= section, "pattern section order differs"); section = next
            if (entry.kind == "builtin") {
                val ordinal = -entry.id.substringAfterLast(':').toInt()
                expect(ordinal > lastBuiltin, "built-in source order differs"); lastBuiltin = ordinal
            }
        }
        val detail = if (root.get("detail") === JSONObject.NULL) null else obj(root.get("detail")).let { row ->
            val metadata = entry(row, true); val raw = values(row.get("values")); val derived = percentages(row.get("percentages"), raw)
            expect(metadata.assignable == (total(raw) > 0), "assignability differs from contributions")
            val bound = obj(row.get("bound_fits")); keys(bound, "offset", "limit", "total", "entries")
            expect(integer(bound.get("offset")) == expected.view.boundOffset && integer(bound.get("limit")) == 50L &&
                integer(bound.get("total")) == metadata.boundFitCount, "bound-fit page differs")
            val fits = OfflineFeatureCodec.rows(bound.get("entries")).map { obj(it).let { item ->
                keys(item, "fit_id", "name", "revision")
                OfflineDamageBoundFit(fitId(item.get("fit_id")), (item.get("name") as? String ?: OfflineFeatureCodec.reject("Damage patterns: fit name must be text")).also { expect(it.isNotEmpty(), "empty fit name") }, integer(item.get("revision"), 1))
            } }
            pageSize(fits.size, expected.view.boundOffset, 50, metadata.boundFitCount)
            expect(fits.map { it.id }.distinct().size == fits.size, "duplicate bound fit")
            entries.find { it.id == metadata.id }?.let { expect(it == metadata, "detail metadata differs") }
            val modulePage = obj(row.get("bound_modules")); keys(modulePage, "offset", "limit", "total", "entries")
            expect(integer(modulePage.get("offset")) == expected.view.moduleOffset && integer(modulePage.get("limit")) == 50L &&
                integer(modulePage.get("total")) == metadata.boundModuleCount, "bound-module page differs")
            val modules = OfflineFeatureCodec.rows(modulePage.get("entries")).map { obj(it).let { holder ->
                keys(holder, "fit_id", "fit_name", "fit_revision", "object_key", "position", "item_id", "name")
                val position = integer(holder.get("position")); val itemId = integer(holder.get("item_id"), 1)
                expect(position <= Int.MAX_VALUE && itemId <= Int.MAX_VALUE, "module identity exceeds Int32")
                OfflineDamageBoundModule(fitId(holder.get("fit_id")), text(holder.get("fit_name")).also { expect(it.isNotEmpty(), "empty holder fit name") },
                    integer(holder.get("fit_revision"), 1), fitId(holder.get("object_key")), position.toInt(), itemId.toInt(),
                    text(holder.get("name")).also { expect(it.isNotBlank(), "empty module name") })
            } }
            pageSize(modules.size, expected.view.moduleOffset, 50, metadata.boundModuleCount)
            expect(modules.map { it.fitId to it.objectKey }.distinct().size == modules.size, "duplicate module holder")
            expect(modules.map { it.fitId to it.position }.distinct().size == modules.size, "duplicate module position")
            val seenFits = mutableSetOf<String>(); var previous: OfflineDamageBoundModule? = null
            modules.forEach { holder ->
                if (holder.fitId == previous?.fitId) expect(holder.position > checkNotNull(previous).position && holder.fitRevision == previous?.fitRevision && holder.fitName == previous?.fitName, "unordered/inconsistent module holders")
                else expect(seenFits.add(holder.fitId), "noncontiguous module holder fit")
                fits.find { it.id == holder.fitId }?.let { expect(it.revision == holder.fitRevision && it.name == holder.fitName, "holder fit metadata differs") }
                previous = holder
            }
            expect((fits.map { it.id } + modules.map { it.fitId }).distinct().size.toLong() <= metadata.affectedFitCount, "affected fit count undercounts visible holders")
            if (expected.view.boundOffset == 0L && expected.view.moduleOffset == 0L && fits.size.toLong() == metadata.boundFitCount && modules.size.toLong() == metadata.boundModuleCount)
                expect((fits.map { it.id } + modules.map { it.fitId }).distinct().size.toLong() == metadata.affectedFitCount, "affected fit union differs")
            OfflineDamageDetail(metadata, raw, derived, expected.view.boundOffset, OfflineFeatureCodec.frozen(fits), expected.view.moduleOffset, OfflineFeatureCodec.frozen(modules))
        }
        if (kind == "named") {
            entries.find { it.id == selectedId }?.let { expect(it.boundFitCount > 0 && it.revision == patternRevision, "named selection differs") }
            detail?.let { if (it.entry.id == selectedId) expect(it.entry.boundFitCount > 0 && it.entry.revision == patternRevision, "named detail differs") }
        }
        detail?.let { currentDetail -> currentDetail.boundFits.find { it.id == fit }?.let {
            expect(kind == "named" && selectedId == currentDetail.entry.id && it.revision == revision, "selected bound fit differs")
        } }
        when (expected.operation) {
            "create", "duplicate" -> expect(detail != null && !detail.entry.readonly, "missing created detail")
            "apply_item" -> expect(detail?.entry?.id == SELECTED_AMMO_PATTERN_ID && selectedId == SELECTED_AMMO_PATTERN_ID, "missing applied Selected Ammo binding/detail")
            "delete" -> {
                val deleted = OfflineFeatureCodec.parse(expected.argumentsJson).getString("pattern_id")
                expect(detail?.entry?.id == expected.view.selectedPatternId?.takeIf { it != deleted }, "deleted detail differs")
            }
            "undo", "redo" -> expect(detail == null || detail.entry.id == expected.view.selectedPatternId, "detail selection differs")
            else -> expect(detail?.entry?.id == expected.view.selectedPatternId, "detail selection differs")
        }
        val item = if (root.get("item") === JSONObject.NULL) null else item(obj(root.get("item")))
        if (expected.operation in setOf("item_options", "apply_item")) {
            val args = OfflineFeatureCodec.parse(expected.argumentsJson)
            expect(item != null && item.itemId.toLong() == integer(args.get("item_id"), 1), "item identity differs")
            val submittedRevision = integer(args.get("fit_revision"), 1)
            expect(fit != null && revision != null && revision >= submittedRevision, "item fit revision differs")
            if (expected.operation == "item_options") expect(revision == submittedRevision, "item preview changed fit revision")
            else {
                expect(item?.available == true && detail?.values == item?.values, "applied contributions differ from item")
            }
        } else expect(item == null, "unexpected item preview")
        val module = if (root.get("module") === JSONObject.NULL) null else ModuleRahCodec.descriptor(root.get("module"))
        if (expected.operation in setOf("module_options", "set_module")) {
            val args = OfflineFeatureCodec.parse(expected.argumentsJson)
            val submittedRevision = integer(args.get("fit_revision"), 1)
            expect(module != null && module.objectKey == fitId(args.get("object_key")) && module.index.toLong() == integer(args.get("position")), "module target differs")
            expect(fit != null && revision != null && revision >= submittedRevision, "module fit revision differs")
            if (expected.operation == "module_options") expect(revision == submittedRevision, "module preview changed fit revision")
            else {
                val selected = obj(args.get("selection")); val actual = checkNotNull(module)
                expect(actual.mode.wire == text(selected.get("mode")), "saved module mode differs")
                when (actual.mode) {
                    RahMode.BUILTIN -> expect(actual.patternId == ModuleRahCodec.builtinId(selected.get("pattern_id")), "saved builtin differs")
                    RahMode.NAMED -> expect(actual.namedId == ModuleRahCodec.namedId(selected.get("pattern_id")) && actual.patternRevision == integer(selected.get("revision"), 1), "saved named pattern differs")
                    else -> Unit
                }
            }
            if (module?.mode == RahMode.NAMED) {
                entries.find { it.id == module.namedId }?.let { expect(it.assignable && it.boundModuleCount > 0 && it.revision == module.patternRevision && it.name == module.patternName, "module page metadata differs") }
                detail?.takeIf { it.entry.id == module.namedId }?.let {
                    expect(it.entry.assignable && it.entry.boundModuleCount > 0 && it.entry.revision == module.patternRevision && it.entry.name == module.patternName, "module detail metadata differs")
                    val amounts = it.values.fields.values.map { number -> number.toDouble() }
                    expect(module.components == RahComponents(amounts[0], amounts[1], amounts[2], amounts[3]), "module components differ")
                }
            }
        } else expect(module == null, "unexpected module descriptor")
        return OfflineDamageState(context, fit, revision, OfflineDamageSelection(kind, selectedId, patternRevision, bindingRevision), expected.view.copy(selectedPatternId = detail?.entry?.id),
            total, OfflineFeatureCodec.frozen(entries), detail, history(root.get("history")), item, module)
    }
    private fun item(row: JSONObject): OfflineDamageItem {
        keys(row, "item_id", "name", "eligible", "available", "unavailable_reason", "values")
        val id = integer(row.get("item_id"), 1).also { expect(it <= Int.MAX_VALUE, "item ID exceeds Int32") }.toInt()
        val label = text(row.get("name")).also { expect(it.isNotEmpty() && it.codePointCount(0, it.length) <= 1024 &&
            it.none { c -> Character.getType(c) == Character.CONTROL.toInt() }, "invalid item name") }
        val eligible = OfflineFeatureCodec.bool(row.get("eligible")); val available = OfflineFeatureCodec.bool(row.get("available"))
        val reason = nullableText(row.get("unavailable_reason"))
        val raw = if (row.get("values") === JSONObject.NULL) null else values(row.get("values"))
        expect(when {
            !eligible -> !available && reason == "no_damage_attributes" && raw == null
            available -> reason == null && raw != null && total(raw) > 0
            reason == "invalid_values" -> raw == null
            reason == "zero_total" -> raw != null && total(raw) == 0.0
            else -> false
        }, "inconsistent item availability")
        return OfflineDamageItem(id, label, eligible, available, reason, raw)
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
        throw BridgeProtocolException("Damage patterns: absent state")
    }
    fun response(raw: String, expected: OfflineDamageRequest): OfflineDamageResponse {
        val row = OfflineFeatureCodec.parse(raw)
        keys(row, "version", "request_id", "ok", "committed", "reopen_required", "state", "bridge", "error")
        expect(integer(row.get("version")) == 3L && text(row.get("request_id")) == expected.requestId, "response identity differs")
        val ok = OfflineFeatureCodec.bool(row.get("ok")); val reopen = OfflineFeatureCodec.bool(row.get("reopen_required"))
        val committed = row.get("committed").let { if (it === JSONObject.NULL) null else OfflineFeatureCodec.bool(it) }
        if (!ok) {
            expect(committed != true && (committed == null) == reopen && row.get("state") === JSONObject.NULL && row.get("bridge") === JSONObject.NULL, "partial/ambiguous failure")
            val error = obj(row.get("error")); keys(error, "code", "message")
            return OfflineDamageResponse(expected.requestId, false, committed, reopen, null, null,
                OfflineFeatureError(text(error.get("code")), text(error.get("message")).also { expect(it.isNotEmpty() && it.codePointCount(0, it.length) <= 1024 && it.none { c -> Character.getType(c) == Character.CONTROL.toInt() }, "invalid error text") }))
        }
        expect(committed != null && !reopen && row.get("error") === JSONObject.NULL, "ambiguous success")
        expect(stateByteCount(raw) <= 524_288, "state exceeds byte limit")
        val state = state(obj(row.get("state")), expected)
        expect(state.context.generation == if (committed == true) Math.addExact(expected.context.generation, 1) else expected.context.generation, "generation differs")
        if (expected.operation in setOf("apply_item", "set_module")) {
            val submitted = integer(OfflineFeatureCodec.parse(expected.argumentsJson).get("fit_revision"), 1)
            val resulting = checkNotNull(state.fitRevision)
            expect(if (committed == true) resulting > submitted else resulting == submitted, "item commit/fit revision differs")
        }
        val bridge = if (damageReadLike(expected.operation)) {
            expect(committed == false && row.get("bridge") === JSONObject.NULL && state.context == expected.context, "read mutated state"); null
        } else {
            if (committed == false) expect(state.context == expected.context, "no-op changed context")
            BridgeCodec.decodeResponse(OfflineFeatureCodec.json(row.get("bridge"))).also {
                expect(it.isSuccess && it.requestId == "bootstrap" && it.sessionId == state.context.sessionId, "invalid committed bridge")
                expect(state.fitId == null || it.fits.any { fit -> fit.id == state.fitId && fit.revision == state.fitRevision }, "selected bridge fit differs")
                state.detail?.boundFits?.forEach { bound -> expect(it.fits.any { fit -> fit.id == bound.id && fit.revision == bound.revision && fit.name == bound.name }, "bound bridge fit differs") }
                state.detail?.boundModules?.forEach { bound -> expect(it.fits.any { fit -> fit.id == bound.fitId && fit.revision == bound.fitRevision && fit.name == bound.fitName }, "module holder bridge fit differs") }
            }
        }
        return OfflineDamageResponse(expected.requestId, true, committed, false, state, bridge, null)
    }
}

/** Serialized runtime publication still defends against late/foreign completions. */
internal fun mayPublishDamageContext(current: OfflineContext?, incoming: OfflineContext): Boolean = current != null &&
    current.sessionId == incoming.sessionId && current.datasetSha256 == incoming.datasetSha256 && incoming.generation >= current.generation
