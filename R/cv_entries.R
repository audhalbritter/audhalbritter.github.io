# Turn a section of resources/cv-entries.yaml into markdown lines.
# Each entry is "date  title, organization, location. description"

entry_text <- function(item, field) {
  value <- item[[field]]
  if (is.null(value) || length(value) == 0) {
    return("")
  }
  as.character(value)
}

write_entries <- function(cv, section) {
  entries <- cv[[section]]
  if (is.null(entries) || length(entries) == 0) {
    return(invisible())
  }
  for (item in entries) {
    parts <- c(
      entry_text(item, "title"),
      entry_text(item, "organization"),
      entry_text(item, "location")
    )
    parts <- parts[nzchar(parts)]
    line <- paste(parts, collapse = ", ")
    dates <- entry_text(item, "dates")
    if (nzchar(dates)) {
      cat("**", dates, "** ", line, sep = "")
    } else {
      cat(line)
    }
    description <- entry_text(item, "description")
    if (nzchar(description)) {
      cat(". ", description, sep = "")
    }
    cat("\n\n")
  }
}
