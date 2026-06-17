import re
import json
import logging
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("uvicorn.error")

class DocumentParserService:
    @staticmethod
    def parse_pdf(file_path: str) -> List[Dict[str, Any]]:
        """
        Parses a PDF file and returns a list of pages with text content.
        """
        pages = []
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            for idx, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and text.strip():
                    pages.append({
                        "page_number": idx + 1,
                        "text": text
                    })
            logger.info(f"Successfully parsed PDF: {file_path}. Total pages: {len(pages)}")
        except Exception as e:
            logger.error(f"Error parsing PDF file {file_path}: {e}")
        return pages

    @staticmethod
    def parse_docx(file_path: str) -> str:
        """
        Parses a DOCX file and returns the raw text.
        """
        text = ""
        try:
            import docx
            doc = docx.Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n\n".join(paragraphs)
            logger.info(f"Successfully parsed DOCX: {file_path}. Characters: {len(text)}")
        except Exception as e:
            logger.error(f"Error parsing DOCX file {file_path}: {e}")
        return text

    @staticmethod
    def parse_url(url: str) -> str:
        """
        Scrapes a URL and returns clean readable text.
        """
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Remove script and style elements
            for script in soup(["script", "style", "meta", "noscript", "header", "footer", "nav"]):
                script.decompose()
                
            text = soup.get_text(separator="\n")
            # Clean up line breaks
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = "\n".join(chunk for chunk in chunks if chunk)
            logger.info(f"Successfully scraped URL: {url}. Length: {len(clean_text)}")
            return clean_text
        except Exception as e:
            logger.error(f"Error scraping URL {url}: {e}")
            raise ValueError(f"Failed to scrape URL {url}: {str(e)}")

    @classmethod
    def split_document_by_boundaries(cls, text: str) -> List[Dict[str, Any]]:
        """
        Splits text into separate blocks based on scheme headers or boundaries.
        Looks for common patterns indicating a scheme start, e.g.:
        - 'Scheme Name: ...'
        - Numbered headings (e.g. '1. Aasara Pension')
        - Lines matching '... Yojana' or '... Scheme'
        """
        # Search for headings or bulleted numbers
        # Let's split by sections starting with: 'Scheme:' or 'Scheme Name:' or 'Name of the Scheme:'
        # or numbered indicators like '1. ', '2. ' at the beginning of a line.
        pattern = r'(?m)^(?:Scheme\s*Name\s*:|Scheme\s*:|Name\s*of\s*the\s*Scheme\s*:|\d+\.\s+[A-Z][A-Za-z\s]{3,40}(?:Yojana|Pension|Scheme|Welfare))'
        
        matches = list(re.finditer(pattern, text))
        if not matches:
            # Fallback: if no clear headers, treat the entire document as a single scheme block
            return [{"text": text, "source_page": 1}]
            
        blocks = []
        for i in range(len(matches)):
            start = matches[i].start()
            end = matches[i+1].start() if i + 1 < len(matches) else len(text)
            
            # Try to guess page number by finding page indicators nearby (dummy or heuristic)
            block_text = text[start:end].strip()
            blocks.append({
                "text": block_text,
                "source_page": 1  # will be overridden by PDF parser page if available
            })
            
        return blocks

    @classmethod
    def structure_scheme_with_llm(cls, raw_text: str, llm_provider: Any, source_page: Optional[int] = None) -> Dict[str, Any]:
        """
        Uses an LLM to parse raw text block into structured scheme schema and eligibility rules.
        """
        system_prompt = (
            "You are a Welfare Scheme Structuring Assistant. Your goal is to parse raw text containing a welfare scheme "
            "into a clean, structured JSON object matching the requested schema.\n"
            "CRITICAL: Output ONLY valid JSON. Do not include markdown code block syntax (like ```json) or explanation."
        )
        
        prompt = f"""
Given the following raw text of a welfare scheme, parse it and extract the fields.

Fields to extract:
1. scheme_name (str): Official name of the scheme.
2. state (str): Andhra Pradesh, Telangana, or Central.
3. category (str): e.g., Pension, Housing, Education, Health, Agriculture, Women, etc.
4. description (str): Summary of what the scheme is.
5. benefits (json/dict): Detailed benefits provided (e.g., {{"amount": 3000, "frequency": "monthly"}}).
6. eligibility_rules (json/dict): A structured set of eligibility criteria matching:
   - min_age (int or null)
   - max_age (int or null)
   - gender_allowed (list of str, e.g. ["female", "any"])
   - max_income (int or null, maximum annual income allowed)
   - occupations (list of str, e.g. ["agriculture", "any"])
   - education_max (str or null)
   - disability_required (bool or null)
   - state (str, e.g. "Telangana" or "Andhra Pradesh")
7. required_documents (list of str): e.g. ["Aadhaar Card", "Income Certificate", "Ration Card"].
8. application_process (str): Steps to apply.

Text to parse:
{raw_text}

JSON Output:
"""
        
        try:
            response_text = llm_provider.generate(prompt=prompt, system_prompt=system_prompt)
            # Remove markdown wraps if present
            clean_json = response_text.strip()
            if clean_json.startswith("```"):
                # strip code block formatting
                clean_json = re.sub(r"^```(?:json)?\n", "", clean_json)
                clean_json = re.sub(r"\n```$", "", clean_json)
                
            data = json.loads(clean_json)
            # Add defaults or metadata
            data["source_page"] = source_page or data.get("source_page", 1)
            data["verification_status"] = "UNVERIFIED"
            return data
        except Exception as e:
            logger.error(f"Failed to structure scheme using LLM: {e}. Falling back to heuristic parsing.")
            return cls._heuristic_structure_fallback(raw_text, source_page)

    @classmethod
    def _heuristic_structure_fallback(cls, raw_text: str, source_page: Optional[int] = None) -> Dict[str, Any]:
        """
        Fallback parser using regex / string operations when LLM is unavailable.
        """
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        scheme_name = lines[0] if lines else "Unknown Scheme"
        
        # Strip common label prefixes
        scheme_name = re.sub(r'^(Scheme\s*Name\s*:|Scheme\s*:|\d+\.\s+)', '', scheme_name).strip()
        
        # Set up a generic template
        return {
            "scheme_name": scheme_name,
            "state": "Telangana" if "telangana" in raw_text.lower() else ("Andhra Pradesh" if "andhra" in raw_text.lower() else "Central"),
            "category": "Welfare",
            "description": raw_text[:200] + "...",
            "benefits": {"details": "Check description for details"},
            "eligibility_rules": {
                "min_age": None,
                "gender_allowed": ["any"],
                "max_income": None,
                "occupations": ["any"],
                "disability_required": None,
                "state": "Telangana" if "telangana" in raw_text.lower() else ("Andhra Pradesh" if "andhra" in raw_text.lower() else "any")
            },
            "required_documents": ["Aadhaar Card"],
            "application_process": "Contact local administration",
            "source_page": source_page or 1,
            "verification_status": "UNVERIFIED"
        }
