
import pypdf
import sys

def extract_first_page(pdf_path):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        reader = pypdf.PdfReader(pdf_path)
        first_page = reader.pages[0]
        text = first_page.extract_text()
        print(text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    extract_first_page("2602.07868v2_copy.pdf")
