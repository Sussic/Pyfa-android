package io.github.sussic.pyfa

data class NoteDetails(val fitId: String, val revision: Long, val text: String,
    val characters: Int, val editable: Boolean)
