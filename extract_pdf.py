import pypdf
import sys

def extract_all_pages(pdf_path, output_path):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        reader = pypdf.PdfReader(pdf_path)
        with open(output_path, 'w', encoding='utf-8') as f:
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    f.write(text + "\n")
        print(f"Extraction complete. Saved to {output_path}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    extract_all_pages("paper.pdf", "paper_text.txt")
