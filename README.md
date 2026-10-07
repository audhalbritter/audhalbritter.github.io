# Aud H. Halbritter

Personal site and CV for Aud Halbritter, built with [Quarto](https://quarto.org).

The pages are the source. `quarto render` writes the HTML website into `docs/`. GitHub Pages can publish that folder, which makes the site available at <https://audhalbritter.github.io>. The domain audhalbritter.com is still the WordPress site until that DNS record is changed.

## Update a publication

Add the DOI to the list in `scripts/build_bibliography.py`, then run:

```bash
python3 scripts/build_bibliography.py
quarto render
```

`resources/works.bib` is the bibliography. The Publications page lists journal articles and data papers in APA style, grouped by year. For 21 or more authors, APA shows the first 19, an ellipsis, and the last author. The same script writes `resources/_journal-articles.md`, which the CV includes in a shorter form, and `resources/_presentations.md`.

## Update the CV

Jobs, grants, teaching, students, and talks live in `resources/cv-entries.yaml`. The CV page is `cv/cv.qmd`.

## Blog

Posts imported from the old WordPress site are in `posts/`. Each post has an alias for its old address. To import again:

```bash
python3 scripts/import_blog.py
```
