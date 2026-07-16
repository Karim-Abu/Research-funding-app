"""One-shot, isolated Word COM conversion for the render smoke test.

Office may leave COM finalizers behind when embedded in pytest's AnyIO process.
The helper exits immediately after orderly Word shutdown so that behavior cannot
affect unrelated test threads.
"""
from __future__ import annotations

import os
import sys

import pythoncom
import win32com.client


def main() -> None:
    docx_path, pdf_path = sys.argv[1:3]
    pythoncom.CoInitialize()
    app = None
    document = None
    try:
        app = win32com.client.DispatchEx("Word.Application")
        app.Visible = False
        app.DisplayAlerts = 0
        document = app.Documents.Open(docx_path, ReadOnly=True)
        document.SaveAs(pdf_path, FileFormat=17)  # wdFormatPDF
    finally:
        if document is not None:
            document.Close(False)
        if app is not None:
            app.Quit()
        pythoncom.CoUninitialize()
    # Avoid pywin32/Office finalizer callbacks leaking into pytest's event loop.
    os._exit(0)


if __name__ == "__main__":
    main()
