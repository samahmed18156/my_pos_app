import ast
from pathlib import Path

def test_supplier_credits_window_keeps_parent_reference():
    src = Path(__file__).parents[1] / 'supplier_credits.py'
    tree = ast.parse(src.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SupplierCreditsWindow')
    init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__init__')
    attrs = []
    for n in ast.walk(init):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == 'self':
                    attrs.append(t.attr)
    assert 'parent' in attrs

def test_supplier_credits_post_uses_parent_safely():
    src = Path(__file__).parents[1] / 'supplier_credits.py'
    text = src.read_text(encoding='utf-8')
    assert "self.parent" in text
    assert "getattr(self.parent,'current_branch_id',1)" in text
    assert "getattr(self.parent,'cashier_username','Unknown')" in text
