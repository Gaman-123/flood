"""
build_tsinghua.py  —  Compiles tsinghua_sssp.cpp as a Python C-Extension
using the same MSVC/compiler toolchain that built Python itself.
Run once with: python build_tsinghua.py build_ext --inplace
"""
from setuptools import setup, Extension
import sys

ext = Extension(
    name='tsinghua_sssp_ext',
    sources=['tsinghua_sssp_ext.cpp'],
    extra_compile_args=['/O2'] if sys.platform == 'win32' else ['-O3', '-std=c++11'],
    language='c++',
)

setup(
    name='tsinghua_sssp_ext',
    ext_modules=[ext],
)
