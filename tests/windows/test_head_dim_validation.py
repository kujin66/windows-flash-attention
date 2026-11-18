"""Exercise the real pure host validator without importing GPU dependencies."""
import ast
from functools import lru_cache
from pathlib import Path

import pytest


@pytest.fixture
def validate():
    source = Path(__file__).resolve().parents[2] / 'flash_attn/cute/interface.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_validate_head_dims')
    namespace = {'lru_cache': lru_cache}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['_validate_head_dims']


@pytest.mark.parametrize('arch', [8, 12])
@pytest.mark.parametrize('dq,dv', [(8, 8), (72, 104), (192, 128), (256, 256), (288, 288), (64, 288), (512, 512)])
def test_positive_aligned_head_dimensions_pass_host_validation(validate, arch, dq, dv):
    validate(dq, dv, arch, 8)


@pytest.mark.parametrize('arch', [8, 12])
@pytest.mark.parametrize('dq,dv', [(4, 4), (148, 148), (64, 4), (64, 148), (0, 64), (64, 0), (-8, 64), (64, -8)])
def test_invalid_head_dimensions_fail_before_dispatch(validate, arch, dq, dv):
    with pytest.raises(AssertionError, match=f'is not supported on SM{arch * 10}'):
        validate(dq, dv, arch, 8)
