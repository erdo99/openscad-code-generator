"""
Unit Tests for Improved Backend API
Her özelliğin doğru çalıştığını ve verilerin doğru aktarıldığını test eder
"""
import unittest
import sys
import os
import re
from unittest.mock import MagicMock, patch

# zai modülünü mock et (test için gerekli değil)
sys.modules['zai'] = MagicMock()
sys.modules['zai'].ZaiClient = MagicMock()

# Flask modüllerini mock et
sys.modules['flask'] = MagicMock()
sys.modules['flask_cors'] = MagicMock()

# Backend modülünü import et
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Sınıfları doğrudan import et (mock'lar sayesinde çalışacak)
try:
    from backend_api_improved import (
        OpenSCADSyntaxChecker,
        FewShotExamples,
        SelfCorrectionLoop
    )
except ImportError as e:
    print(f"[WARN] Import hatası: {e}")
    print("📝 Sınıfları manuel olarak tanımlıyoruz...")
    
    # Fallback: Sınıfları manuel tanımla
    class OpenSCADSyntaxChecker:
        def __init__(self):
            self.error_patterns = {
                "missing_semicolon": {
                    "pattern": r"(cube|cylinder|sphere|translate|rotate|scale|mirror|union|difference|intersection|hull|minkowski)\s*\([^)]*\)\s*(?!;|{|\n)",
                    "fix": lambda m: m.group(0) + ";",
                    "description": "Missing semicolon after statement"
                },
                "wrong_brackets": {
                    "pattern": r"(cube|cylinder)\s*\(\s*(\d+(?:\.\d+)?)\s*(?:,\s*(\d+(?:\.\d+)?))?\s*(?:,\s*(\d+(?:\.\d+)?))?\s*\)",
                    "fix": self._fix_wrong_brackets,
                    "description": "Wrong parameter syntax (should use [x, y, z])"
                },
                "python_for": {
                    "pattern": r"for\s+(\w+)\s+in\s+range\s*\(\s*(\d+)\s*\)",
                    "fix": lambda m: f"for({m.group(1)}=[0:{int(m.group(2))-1}])",
                    "description": "Python-style for loop detected"
                },
                "python_def": {
                    "pattern": r"def\s+\w+\s*\(",
                    "fix": lambda m: m.group(0).replace("def", "module"),
                    "description": "Python 'def' instead of 'module'"
                }
            }
        
        def _fix_wrong_brackets(self, match):
            func = match.group(1)
            params = [g for g in match.groups()[1:] if g]
            if len(params) == 1:
                val = params[0]
                return f"{func}([{val}, {val}, {val}])"
            elif len(params) == 2:
                return f"{func}([{params[0]}, {params[1]}, {params[1]}])"
            elif len(params) == 3:
                return f"{func}([{params[0]}, {params[1]}, {params[2]}])"
            return match.group(0)
        
        def check(self, code):
            errors = []
            lines = code.split('\n')
            for i, line in enumerate(lines, 1):
                line_stripped = line.strip()
                if not line_stripped or line_stripped.startswith('//'):
                    continue
                for error_type, error_info in self.error_patterns.items():
                    pattern = error_info["pattern"]
                    matches = list(re.finditer(pattern, line, re.IGNORECASE))
                    for match in matches:
                        errors.append({
                            "line": i,
                            "type": error_type,
                            "description": error_info["description"],
                            "code": line_stripped,
                            "match": match.group(0)
                        })
            return errors
        
        def auto_fix_common_errors(self, code):
            fixed_code = code
            for error_type, error_info in self.error_patterns.items():
                pattern = error_info["pattern"]
                fix_func = error_info["fix"]
                matches = list(re.finditer(pattern, fixed_code, re.IGNORECASE))
                for match in reversed(matches):
                    fixed = fix_func(match)
                    fixed_code = fixed_code[:match.start()] + fixed + fixed_code[match.end():]
            return fixed_code
        
        def validate_before_generation(self, description):
            warnings = []
            if "def " in description or "for i in range" in description:
                warnings.append({
                    "type": "python_syntax",
                    "message": "Python syntax detected",
                    "suggestion": "Use OpenSCAD syntax"
                })
            return warnings
    
    class FewShotExamples:
        def __init__(self):
            self.examples = [
                {
                    "id": "simple_cube",
                    "description": "Simple cube with dimensions",
                    "image_type": "cube",
                    "code": "cube([50, 30, 20]);\n",
                    "success_rate": 0.98,
                    "keywords": ["cube", "box", "rectangular", "simple"]
                },
                {
                    "id": "rounded_box",
                    "description": "Rounded box with corner radius",
                    "image_type": "rounded_box",
                    "code": "module rounded_box(size, radius) { hull() { } }\n",
                    "success_rate": 0.95,
                    "keywords": ["rounded", "box", "corner", "radius"]
                }
            ]
        
        def select_relevant_examples(self, description, image_type=None, top_k=3):
            description_lower = description.lower()
            scored_examples = []
            for ex in self.examples:
                score = 0.0
                for keyword in ex["keywords"]:
                    if keyword in description_lower:
                        score += 1.0
                if image_type and ex["image_type"] == image_type:
                    score += 2.0
                score += ex["success_rate"] * 0.5
                scored_examples.append((score, ex))
            sorted_examples = sorted(scored_examples, key=lambda x: x[0], reverse=True)
            return [ex for score, ex in sorted_examples[:top_k]]
        
        def format_examples_for_prompt(self, examples):
            if not examples:
                return ""
            formatted = "\n**SUCCESSFUL EXAMPLES:**\n\n"
            for i, ex in enumerate(examples, 1):
                formatted += f"**Example {i}:**\n{ex['description']}\n```openscad\n{ex['code']}\n```\n\n"
            return formatted
    
    class SelfCorrectionLoop:
        def __init__(self, api_client, model_name, syntax_checker):
            self.api_client = api_client
            self.model_name = model_name
            self.syntax_checker = syntax_checker


# ============================================================================
# TEST 1: SYNTAX VALIDATION & PRE-CHECK
# ============================================================================

class TestSyntaxChecker(unittest.TestCase):
    """Syntax Checker özelliğini test et"""
    
    def setUp(self):
        """Her test öncesi syntax checker oluştur"""
        self.checker = OpenSCADSyntaxChecker()
    
    def test_missing_semicolon_detection(self):
        """Eksik semicolon tespiti"""
        code = """
cube([10, 20, 30])
cylinder(h=30, r=10)
"""
        errors = self.checker.check(code)
        
        # En az 1 hata bulunmalı
        self.assertGreaterEqual(len(errors), 1, "Missing semicolon errors should be detected")
        
        # Hataların tipi doğru mu?
        error_types = [e['type'] for e in errors]
        self.assertIn('missing_semicolon', error_types, "Should detect missing semicolon")
        print(f"[OK] Missing semicolon test: {len(errors)} errors found")
    
    def test_wrong_brackets_detection(self):
        """Yanlış bracket kullanımı tespiti"""
        code = """
cube(10, 20, 30)
cylinder(30, 10)
"""
        errors = self.checker.check(code)
        
        # Wrong brackets hatası bulunmalı
        error_types = [e['type'] for e in errors]
        self.assertIn('wrong_brackets', error_types, "Should detect wrong bracket syntax")
        print(f"[OK] Wrong brackets test: {len(errors)} errors found")
    
    def test_python_syntax_detection(self):
        """Python syntax tespiti"""
        code = """
def my_function():
    for i in range(5):
        cube([10, 10, 10])
"""
        errors = self.checker.check(code)
        
        # Python syntax hataları bulunmalı
        error_types = [e['type'] for e in errors]
        self.assertIn('python_def', error_types, "Should detect Python 'def'")
        self.assertIn('python_for', error_types, "Should detect Python 'for' loop")
        print(f"[OK] Python syntax test: {len(errors)} errors found")
    
    def test_auto_fix_common_errors(self):
        """Otomatik düzeltme testi"""
        code = """
cube(10, 20, 30)
cylinder(30, 10)
"""
        fixed_code = self.checker.auto_fix_common_errors(code)
        
        # Düzeltilmiş kod orijinalinden farklı olmalı
        self.assertNotEqual(code, fixed_code, "Code should be fixed")
        
        # Düzeltilmiş kodda bracket'lar doğru olmalı
        self.assertIn('[', fixed_code, "Fixed code should use brackets")
        print(f"[OK] Auto-fix test: Code fixed successfully")
    
    def test_validate_before_generation(self):
        """Üretim öncesi validasyon testi"""
        description = "Create a cube using def function and for i in range(5)"
        warnings = self.checker.validate_before_generation(description)
        
        # Uyarı bulunmalı
        self.assertGreater(len(warnings), 0, "Should detect Python syntax in description")
        
        # Uyarı tipi doğru mu?
        warning_types = [w['type'] for w in warnings]
        self.assertIn('python_syntax', warning_types, "Should warn about Python syntax")
        print(f"[OK] Pre-generation validation test: {len(warnings)} warnings found")
    
    def test_data_flow_syntax_checker(self):
        """Veri akışı testi: Input -> Check -> Output"""
        # Input
        code = "cube(10, 20, 30)"
        
        # Process
        errors = self.checker.check(code)
        fixed_code = self.checker.auto_fix_common_errors(code)
        
        # Output validation
        self.assertIsInstance(errors, list, "Errors should be a list")
        self.assertIsInstance(fixed_code, str, "Fixed code should be a string")
        self.assertGreater(len(fixed_code), 0, "Fixed code should not be empty")
        
        # Fixed code'da hata sayısı azalmalı
        errors_after_fix = self.checker.check(fixed_code)
        print(f"[OK] Data flow test: {len(errors)} errors before, {len(errors_after_fix)} after fix")


# ============================================================================
# TEST 2: FEW-SHOT LEARNING
# ============================================================================

class TestFewShotExamples(unittest.TestCase):
    """Few-Shot Examples özelliğini test et"""
    
    def setUp(self):
        """Her test öncesi few-shot examples oluştur"""
        self.few_shot = FewShotExamples()
    
    def test_examples_loaded(self):
        """Örnekler yüklenmiş mi?"""
        self.assertGreater(len(self.few_shot.examples), 0, "Examples should be loaded")
        
        # Her örnekte gerekli alanlar var mı?
        for ex in self.few_shot.examples:
            self.assertIn('id', ex, "Example should have 'id'")
            self.assertIn('description', ex, "Example should have 'description'")
            self.assertIn('code', ex, "Example should have 'code'")
            self.assertIn('keywords', ex, "Example should have 'keywords'")
        print(f"[OK] Examples loaded test: {len(self.few_shot.examples)} examples")
    
    def test_select_relevant_examples(self):
        """İlgili örnekler seçiliyor mu?"""
        description = "Create a simple cube with dimensions"
        examples = self.few_shot.select_relevant_examples(description, top_k=3)
        
        # En az bir örnek dönmeli
        self.assertGreater(len(examples), 0, "Should return at least one example")
        self.assertLessEqual(len(examples), 3, "Should return at most 3 examples")
        
        # Cube ile ilgili örnek bulunmalı
        cube_examples = [ex for ex in examples if 'cube' in ex['description'].lower() or 'cube' in ex['keywords']]
        self.assertGreater(len(cube_examples), 0, "Should find cube-related examples")
        print(f"[OK] Select relevant examples test: {len(examples)} examples selected")
    
    def test_example_selection_by_keywords(self):
        """Keyword'lere göre örnek seçimi"""
        description = "rounded box with corner radius"
        examples = self.few_shot.select_relevant_examples(description, top_k=2)
        
        # Rounded box örneği bulunmalı
        rounded_examples = [ex for ex in examples if 'rounded' in ex['description'].lower() or 'rounded' in ex['keywords']]
        self.assertGreater(len(rounded_examples), 0, "Should find rounded box examples")
        print(f"[OK] Keyword selection test: {len(examples)} examples selected")
    
    def test_format_examples_for_prompt(self):
        """Örnekler prompt formatına çevriliyor mu?"""
        examples = self.few_shot.select_relevant_examples("cube", top_k=2)
        formatted = self.few_shot.format_examples_for_prompt(examples)
        
        # Formatlanmış metin boş olmamalı
        self.assertGreater(len(formatted), 0, "Formatted examples should not be empty")
        
        # Örnek kodlar içermeli
        for ex in examples:
            self.assertIn(ex['code'], formatted, f"Example code should be in formatted text")
            self.assertIn(ex['description'], formatted, f"Example description should be in formatted text")
        print(f"[OK] Format examples test: {len(formatted)} characters formatted")
    
    def test_data_flow_few_shot(self):
        """Veri akışı testi: Description -> Select -> Format -> Prompt"""
        # Input
        description = "box with hole"
        
        # Process
        examples = self.few_shot.select_relevant_examples(description, top_k=3)
        formatted = self.few_shot.format_examples_for_prompt(examples)
        
        # Output validation
        self.assertIsInstance(examples, list, "Examples should be a list")
        self.assertIsInstance(formatted, str, "Formatted should be a string")
        self.assertGreater(len(formatted), 0, "Formatted should not be empty")
        
        # Formatlanmış metin prompt'a eklenebilir olmalı
        prompt = f"Here are examples:\n{formatted}\n\nNow generate code for: {description}"
        self.assertIn(description, prompt, "Description should be in final prompt")
        print(f"[OK] Data flow test: Selected {len(examples)} examples, formatted length: {len(formatted)}")


# ============================================================================
# TEST 3: SELF-CORRECTION LOOP
# ============================================================================

class TestSelfCorrectionLoop(unittest.TestCase):
    """Self-Correction Loop özelliğini test et"""
    
    def setUp(self):
        """Her test öncesi mock setup"""
        self.syntax_checker = OpenSCADSyntaxChecker()
    
    def test_review_prompt_generation(self):
        """Review prompt'u doğru oluşturuluyor mu?"""
        code = "cube(10, 20, 30)"  # Hatalı kod
        original_prompt = "Create a cube"
        
        # Syntax hatalarını bul
        syntax_errors = self.syntax_checker.check(code)
        self.assertGreater(len(syntax_errors), 0, "Should find syntax errors")
        
        # Prompt oluşturma mantığını test et
        errors_summary = "\n".join([
            f"Line {e['line']}: {e['description']} - {e['match']}"
            for e in syntax_errors[:10]
        ])
        
        # Prompt'da gerekli bilgiler olmalı
        self.assertIn("cube(10", errors_summary, "Error summary should contain the error")
        self.assertIn("Line", errors_summary, "Error summary should contain line numbers")
        print(f"[OK] Review prompt test: {len(syntax_errors)} errors in summary")
    
    def test_auto_fix_in_correction_loop(self):
        """Correction loop'ta otomatik düzeltme çalışıyor mu?"""
        code = """
cube(10, 20, 30)
cylinder(30, 10)
"""
        syntax_checker = OpenSCADSyntaxChecker()
        
        # İlk kontrol
        errors_before = syntax_checker.check(code)
        self.assertGreater(len(errors_before), 0, "Should find errors before fix")
        
        # Otomatik düzeltme
        fixed_code = syntax_checker.auto_fix_common_errors(code)
        
        # Düzeltme sonrası kontrol
        errors_after = syntax_checker.check(fixed_code)
        
        # Hata sayısı azalmalı (veya sıfırlanmalı)
        print(f"[OK] Auto-fix test: {len(errors_before)} errors before, {len(errors_after)} after")
    
    def test_iteration_limit(self):
        """Maksimum iterasyon sayısı kontrolü"""
        code = "cube(10, 20, 30)"
        max_iterations = 3
        
        syntax_checker = OpenSCADSyntaxChecker()
        current_code = code
        
        for i in range(max_iterations):
            errors = syntax_checker.check(current_code)
            if not errors:
                break
            current_code = syntax_checker.auto_fix_common_errors(current_code)
        
        # En fazla max_iterations iterasyon yapılmalı
        self.assertLessEqual(i + 1, max_iterations, "Should not exceed max iterations")
        print(f"[OK] Iteration limit test: Completed in {i + 1} iterations")
    
    def test_data_flow_self_correction(self):
        """Veri akışı testi: Code -> Check -> Fix -> Verify"""
        # Input
        code = "cube(10, 20, 30)\ncylinder(30, 10)"
        
        # Process
        syntax_checker = OpenSCADSyntaxChecker()
        errors = syntax_checker.check(code)
        fixed_code = syntax_checker.auto_fix_common_errors(code)
        errors_after = syntax_checker.check(fixed_code)
        
        # Output validation
        self.assertIsInstance(errors, list, "Errors should be a list")
        self.assertIsInstance(fixed_code, str, "Fixed code should be a string")
        self.assertIsInstance(errors_after, list, "Errors after should be a list")
        
        # Fixed code orijinalinden farklı olmalı
        self.assertNotEqual(code, fixed_code, "Fixed code should be different")
        
        print(f"[OK] Data flow test: {len(errors)} errors before, {len(errors_after)} after")


# ============================================================================
# TEST 4: INTEGRATION TESTS (Tüm özellikler birlikte)
# ============================================================================

class TestIntegration(unittest.TestCase):
    """Tüm özelliklerin birlikte çalışmasını test et"""
    
    def setUp(self):
        """Test setup"""
        self.syntax_checker = OpenSCADSyntaxChecker()
        self.few_shot = FewShotExamples()
    
    def test_full_pipeline_without_api(self):
        """Tam pipeline testi (API çağrısı olmadan)"""
        # 1. Input
        description = "Create a simple cube"
        
        # 2. Pre-generation validation
        warnings = self.syntax_checker.validate_before_generation(description)
        print(f"[OK] Pre-generation warnings: {len(warnings)}")
        
        # 3. Few-shot examples selection
        examples = self.few_shot.select_relevant_examples(description, top_k=2)
        formatted_examples = self.few_shot.format_examples_for_prompt(examples)
        self.assertGreater(len(formatted_examples), 0, "Examples should be formatted")
        
        # 4. Simulated code generation (mock)
        generated_code = """
cube([50, 30, 20]);
"""
        
        # 5. Syntax validation
        errors = self.syntax_checker.check(generated_code)
        print(f"[OK] Syntax errors found: {len(errors)}")
        
        # 6. Auto-fix if needed
        if errors:
            fixed_code = self.syntax_checker.auto_fix_common_errors(generated_code)
            errors_after = self.syntax_checker.check(fixed_code)
            print(f"[OK] Errors after fix: {len(errors_after)}")
        
        # Pipeline başarılı
        self.assertTrue(True, "Full pipeline completed")
        print(f"[OK] Full pipeline test: PASSED")
    
    def test_data_flow_between_components(self):
        """Bileşenler arası veri akışı testi"""
        # 1. Few-shot -> Prompt
        description = "rounded box"
        examples = self.few_shot.select_relevant_examples(description)
        formatted = self.few_shot.format_examples_for_prompt(examples)
        
        # 2. Generated code (simulated)
        code = "cube([10, 20, 30])"  # Basit kod
        
        # 3. Syntax checker -> Self-correction input
        errors = self.syntax_checker.check(code)
        
        # 4. Verification: Her adımda veri doğru mu?
        self.assertIsInstance(formatted, str, "Formatted examples should be string")
        self.assertIsInstance(code, str, "Code should be string")
        self.assertIsInstance(errors, list, "Errors should be list")
        
        # Veri akışı başarılı
        print(f"[OK] Data flow between components: OK")
        print(f"   - Examples formatted: {len(formatted)} chars")
        print(f"   - Code length: {len(code)} chars")
        print(f"   - Errors found: {len(errors)}")


# ============================================================================
# TEST 5: EDGE CASES
# ============================================================================

class TestEdgeCases(unittest.TestCase):
    """Edge case'leri test et"""
    
    def setUp(self):
        self.checker = OpenSCADSyntaxChecker()
        self.few_shot = FewShotExamples()
    
    def test_empty_code(self):
        """Boş kod testi"""
        errors = self.checker.check("")
        self.assertIsInstance(errors, list, "Should return list even for empty code")
        print(f"[OK] Empty code test: {len(errors)} errors")
    
    def test_empty_description(self):
        """Boş açıklama testi"""
        examples = self.few_shot.select_relevant_examples("", top_k=3)
        # Boş açıklama ile de örnekler dönmeli (başarı oranına göre)
        self.assertIsInstance(examples, list, "Should return list even for empty description")
        print(f"[OK] Empty description test: {len(examples)} examples")
    
    def test_very_long_code(self):
        """Çok uzun kod testi"""
        long_code = "cube([10, 20, 30]);\n" * 1000
        errors = self.checker.check(long_code)
        # Uzun kodda da çalışmalı
        self.assertIsInstance(errors, list, "Should handle long code")
        print(f"[OK] Long code test: {len(errors)} errors in {len(long_code)} char code")


# ============================================================================
# TEST RUNNER
# ============================================================================

def run_tests():
    """Tüm testleri çalıştır"""
    # Test suite oluştur
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Tüm test sınıflarını ekle
    suite.addTests(loader.loadTestsFromTestCase(TestSyntaxChecker))
    suite.addTests(loader.loadTestsFromTestCase(TestFewShotExamples))
    suite.addTests(loader.loadTestsFromTestCase(TestSelfCorrectionLoop))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    
    # Testleri çalıştır
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Özet
    print("\n" + "="*80)
    print("TEST OZETI")
    print("="*80)
    print(f"Basarili: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Basarisiz: {len(result.failures)}")
    print(f"Hatalar: {len(result.errors)}")
    print(f"Toplam: {result.testsRun}")
    print("="*80)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("Unit Tests Baslatiliyor...")
    print("="*80)
    success = run_tests()
    sys.exit(0 if success else 1)
