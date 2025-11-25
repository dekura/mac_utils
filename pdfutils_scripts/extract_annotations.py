#!/usr/bin/env python3
"""
Extract annotations from a PDF file
"""
import pymupdf  # PyMuPDF
import sys
import json
from datetime import datetime

def extract_annotations(pdf_path, output_format='txt'):
    """
    Extract all annotations from a PDF file

    Args:
        pdf_path: Path to the PDF file
        output_format: 'txt', 'json', or 'markdown'
    """
    doc = pymupdf.open(pdf_path)
    annotations = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        annot_list = page.annots()

        if annot_list:
            for annot in annot_list:
                annot_info = {
                    'page': page_num + 1,
                    'type': annot.type[1],  # Annotation type name
                    'content': annot.info.get('content', ''),
                    'subject': annot.info.get('subject', ''),
                    'author': annot.info.get('title', ''),
                    'date': annot.info.get('creationDate', ''),
                }

                # Get the highlighted/underlined text if applicable
                if annot.type[0] in [8, 9, 10, 11]:  # Highlight, Underline, Squiggly, StrikeOut
                    try:
                        # Get the quad points (coordinates of highlighted text)
                        quads = annot.vertices
                        if quads:
                            # Extract text from the highlighted region
                            rect = annot.rect
                            highlighted_text = page.get_textbox(rect)
                            annot_info['highlighted_text'] = highlighted_text.strip()
                    except:
                        pass

                annotations.append(annot_info)

    doc.close()

    # Output based on format
    if output_format == 'json':
        return json.dumps(annotations, indent=2, ensure_ascii=False)
    elif output_format == 'markdown':
        output = f"# PDF Annotations\n\n**File:** {pdf_path}\n\n"
        output += f"**Total annotations:** {len(annotations)}\n\n---\n\n"

        for i, annot in enumerate(annotations, 1):
            output += f"## Annotation {i}\n\n"
            output += f"- **Page:** {annot['page']}\n"
            output += f"- **Type:** {annot['type']}\n"
            if annot.get('author'):
                output += f"- **Author:** {annot['author']}\n"
            if annot.get('date'):
                output += f"- **Date:** {annot['date']}\n"
            if annot.get('subject'):
                output += f"- **Subject:** {annot['subject']}\n"
            if annot.get('highlighted_text'):
                output += f"- **Highlighted Text:**\n  > {annot['highlighted_text']}\n"
            if annot.get('content'):
                output += f"- **Comment:**\n  ```\n  {annot['content']}\n  ```\n"
            output += "\n---\n\n"

        return output
    else:  # txt format
        output = f"PDF Annotations from: {pdf_path}\n"
        output += f"Total annotations: {len(annotations)}\n"
        output += "="*80 + "\n\n"

        for i, annot in enumerate(annotations, 1):
            output += f"[{i}] Page {annot['page']} - {annot['type']}\n"
            if annot.get('author'):
                output += f"    Author: {annot['author']}\n"
            if annot.get('date'):
                output += f"    Date: {annot['date']}\n"
            if annot.get('subject'):
                output += f"    Subject: {annot['subject']}\n"
            if annot.get('highlighted_text'):
                output += f"    Highlighted: {annot['highlighted_text']}\n"
            if annot.get('content'):
                output += f"    Comment: {annot['content']}\n"
            output += "\n" + "-"*80 + "\n\n"

        return output

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python extract_annotations.py <pdf_file> [output_format]")
        print("Output formats: txt (default), json, markdown")
        sys.exit(1)

    pdf_file = sys.argv[1]
    output_format = sys.argv[2] if len(sys.argv) > 2 else 'txt'

    try:
        result = extract_annotations(pdf_file, output_format)
        print(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
