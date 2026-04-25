"""Canonical demo project seed content.

The single source of truth for ``notes_app`` (and any future demo
project) file trees. Imported by:

  * ``routes/projects.py`` — to serve the ``POST /projects/{id}/reset-to-seed``
    button click.
  * ``scripts/seed_example_project.py`` — to populate a freshly created
    project, by calling the same reset endpoint.
"""
