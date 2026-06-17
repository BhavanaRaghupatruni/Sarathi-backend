from typing import Dict, Any, List, Tuple
import logging

logger = logging.getLogger("uvicorn.error")

class EligibilityService:
    @staticmethod
    def extract_available_documents(profile: Dict[str, Any]) -> List[str]:
        """
        Maps boolean or YES/NO document flags in the citizen profile
        to standardized document names.
        """
        doc_mapping = {
            "doc_aadhaar_available": "Aadhaar Card",
            "doc_pan_available": "PAN Card",
            "doc_rationCard_available": "Ration Card",
            "doc_incomeCert_available": "Income Certificate",
            "doc_casteCert_available": "Caste Certificate",
            "doc_disabilityCert_available": "Disability Certificate",
            "doc_voterId_available": "Voter ID",
            "doc_bankPassbook_available": "Bank Passbook"
        }
        
        available = []
        for key, display_name in doc_mapping.items():
            val = profile.get(key)
            if val == "YES" or val is True:
                available.append(display_name)
                
        # Also check if they passed raw names list
        additional = profile.get("available_documents")
        if isinstance(additional, list):
            available.extend(additional)
            
        return list(set(available))

    @classmethod
    def evaluate_scheme(cls, profile: Dict[str, Any], scheme: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates a single scheme's rules against a citizen profile.
        Returns eligibility status, score, reasons, missing documents, and next steps.
        """
        rules = scheme.get("eligibility_rules", {})
        scheme_name = scheme.get("scheme_name", "Unknown Scheme")
        required_docs = scheme.get("required_documents", [])
        if isinstance(required_docs, str):
            try:
                required_docs = json.loads(required_docs)
            except Exception:
                required_docs = [required_docs]
                
        available_docs = cls.extract_available_documents(profile)
        
        # Parse profile variables
        age = profile.get("age")
        if age is not None:
            try:
                age = int(age)
            except ValueError:
                age = None
        gender = str(profile.get("gender") or "any").lower().strip()
        state = str(profile.get("state") or "").lower().strip()
        income = profile.get("annualIncome") or profile.get("income")
        if income is not None:
            try:
                income = float(income)
            except ValueError:
                income = None
        occupation = str(profile.get("mainOccupation") or "any").lower().strip()
        disability = profile.get("disability") or False
        # Also check if disabilites list is present and non-empty in survey data
        if profile.get("disabilities") and len(profile.get("disabilities", [])) > 0:
            disability = True

        reasons = []
        ineligible_reasons = []
        score = 100
        
        # 1. State check (Critical parameter)
        rule_state = str(rules.get("state") or "any").lower().strip()
        if rule_state != "any" and state != "any" and state != "":
            if rule_state not in state and state not in rule_state:
                ineligible_reasons.append(f"Scheme is restricted to {rules.get('state')}, but citizen resides in {profile.get('state')}.")
                score = 0
                
        # 2. Age check
        min_age = rules.get("min_age")
        max_age = rules.get("max_age")
        if age is not None:
            if min_age is not None and age < int(min_age):
                ineligible_reasons.append(f"Minimum age required is {min_age}, but citizen is {age} years old.")
                score = min(score, 40)
            if max_age is not None and age > int(max_age):
                ineligible_reasons.append(f"Maximum age allowed is {max_age}, but citizen is {age} years old.")
                score = min(score, 40)
                
        # 3. Income check
        max_income = rules.get("max_income")
        if max_income is not None and income is not None:
            if income > float(max_income):
                ineligible_reasons.append(f"Annual income must be below ₹{max_income}, but citizen's income is ₹{income}.")
                score = min(score, 30)
                
        # 4. Gender check
        rule_genders = rules.get("gender_allowed") or ["any"]
        if isinstance(rule_genders, str):
            rule_genders = [rule_genders]
        rule_genders = [g.lower().strip() for g in rule_genders]
        if "any" not in rule_genders:
            matched_gender = False
            for g in rule_genders:
                if g in gender or gender in g:
                    matched_gender = True
                    break
            if not matched_gender:
                ineligible_reasons.append(f"Scheme is restricted to {', '.join(rule_genders)}, but citizen's gender is {profile.get('gender')}.")
                score = 0

        # 5. Disability check
        disability_req = rules.get("disability_required")
        if disability_req is True and not disability:
            ineligible_reasons.append("This scheme requires a disability status, but citizen has none.")
            score = 0

        # 6. Occupation check
        rule_occupations = rules.get("occupations") or ["any"]
        if isinstance(rule_occupations, str):
            rule_occupations = [rule_occupations]
        rule_occupations = [o.lower().strip() for o in rule_occupations]
        if "any" not in rule_occupations:
            matched_occ = False
            for o in rule_occupations:
                if o in occupation or occupation in o:
                    matched_occ = True
                    break
            if not matched_occ:
                # Deduct score instead of disqualifying outright, unless critical
                reasons.append(f"Citizen occupation '{profile.get('mainOccupation')}' does not match scheme occupations: {', '.join(rule_occupations)}.")
                score = min(score, 70)

        # Document Gap Analysis
        missing_docs = []
        for req_doc in required_docs:
            # Check overlap or standard names
            has_doc = False
            for av_doc in available_docs:
                if req_doc.lower().replace(" ", "") in av_doc.lower().replace(" ", "") or av_doc.lower().replace(" ", "") in req_doc.lower().replace(" ", ""):
                    has_doc = True
                    break
            if not has_doc:
                missing_docs.append(req_doc)

        # Deduct score slightly for missing documents but don't disqualify eligibility status
        if missing_docs:
            score = max(score - (10 * len(missing_docs)), 20)

        # Determine overall category
        if score == 0 or len(ineligible_reasons) > 0:
            status = "NOT_ELIGIBLE"
            why_recommended = " / ".join(ineligible_reasons)
        elif score >= 80 and not missing_docs:
            status = "ELIGIBLE"
            why_recommended = f"Fits demographic filters (state, age, income) for {scheme_name} and has all required documents."
        else:
            status = "PARTIALLY_ELIGIBLE"
            why_recommended = " / ".join(ineligible_reasons + reasons)
            if missing_docs:
                why_recommended += f" Missing documents: {', '.join(missing_docs)}."

        # Next steps generation
        if missing_docs:
            next_steps = f"Apply for missing documents ({', '.join(missing_docs)}) at your local secretariat or Meeseva. Then proceed to apply."
        else:
            next_steps = f"Apply online or visit the local secretariat/representative to submit documents and enroll in the scheme."

        return {
            "scheme_name": scheme_name,
            "eligibility_status": status,
            "eligibility_score": score,
            "why_recommended": why_recommended,
            "missing_documents": missing_docs,
            "next_steps": next_steps,
            "source_page": scheme.get("source_page", 1),
            "verification_status": scheme.get("verification_status", "UNVERIFIED")
        }
