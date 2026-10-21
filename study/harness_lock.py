"""Measured Linux CPython 3.12 wheel lock; no candidate imports or code execution.

Resolved 2026-10-21 from PyPI binary wheels. Kept as an owned Python data file so
Docker's existing study/*.py allowlist includes it without widening build context.
"""
import argparse
import hashlib
from pathlib import Path

WHEELS = [{'name': 'distlib',
  'version': '0.4.4',
  'filename': 'distlib-0.4.4-py2.py3-none-any.whl',
  'sha256': 'cf09d55b1e85a89576b036aeb71550bfd68320f3f21761ca329eadadad918638',
  'license': 'PSF-2.0'},
 {'name': 'filelock',
  'version': '4.2.4',
  'filename': 'filelock-4.2.4-py3-none-any.whl',
  'sha256': '301241438c57936ef93f4243a94f2559022268bfcf9b375a9a72eb0f8db8358e',
  'license': 'MIT'},
 {'name': 'greenlet',
  'version': '3.5.6',
  'filename': 'greenlet-3.5.6-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl',
  'sha256': '975736b002ed080d124cf81a79cb7e05cb26d6b3f5c7a7b651c0fcce70353aa1',
  'license': 'MIT AND PSF-2.0'},
 {'name': 'iniconfig',
  'version': '2.3.1',
  'filename': 'iniconfig-2.3.1-py3-none-any.whl',
  'sha256': '9121e2c1fdb355232495be3194c8dfe87ccc2d5dee45947b78e68f499790d7a7',
  'license': 'MIT'},
 {'name': 'packaging',
  'version': '26.3',
  'filename': 'packaging-26.3-py3-none-any.whl',
  'sha256': 'd7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c',
  'license': 'Apache-2.0 OR BSD-2-Clause'},
 {'name': 'pip',
  'version': '26.2.2',
  'filename': 'pip-26.2.2-py3-none-any.whl',
  'sha256': 'fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70',
  'license': 'MIT'},
 {'name': 'platformdirs',
  'version': '4.13.5',
  'filename': 'platformdirs-4.13.5-py3-none-any.whl',
  'sha256': '53d3ec4280b815c1e0b02edad7f9ee8fda1ba9c0865dd9c2e6e63849ce82fc1e',
  'license': 'MIT'},
 {'name': 'playwright',
  'version': '1.64.0',
  'filename': 'playwright-1.64.0-py3-none-manylinux1_x86_64.whl',
  'sha256': '5a59af1b230b234008524a5d42b613b233d4256f73bc1dd25bf3f11db0c81b75',
  'license': 'Apache-2.0'},
 {'name': 'pluggy',
  'version': '1.7.0',
  'filename': 'pluggy-1.7.0-py3-none-any.whl',
  'sha256': '7dd7b0d8832ba3cb632c306926ded123429211b83641b35dc5c41ad2d34f9bec',
  'license': 'MIT'},
 {'name': 'psutil',
  'version': '7.2.2',
  'filename': 'psutil-7.2.2-cp36-abi3-manylinux2010_x86_64.manylinux_2_12_x86_64.manylinux_2_28_x86_64.whl',
  'sha256': '076a2d2f923fd4821644f5ba89f059523da90dc9014e85f8e45a5774ca5bc6f9',
  'license': 'BSD-3-Clause'},
 {'name': 'pyee',
  'version': '14.0.0',
  'filename': 'pyee-14.0.0-py3-none-any.whl',
  'sha256': '3ac2d3229a9677f7de2c33d7f52fe25b638a46b19c413fea2edc8c6d0a644e4d',
  'license': 'MIT'},
 {'name': 'Pygments',
  'version': '2.21.0',
  'filename': 'pygments-2.21.0-py3-none-any.whl',
  'sha256': '2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9',
  'license': 'BSD-2-Clause'},
 {'name': 'pytest',
  'version': '9.1.1',
  'filename': 'pytest-9.1.1-py3-none-any.whl',
  'sha256': '37a86b45efb9a47a61a36449063e8e18d0cab3161329fc099eb21783169c4f0c',
  'license': 'MIT'},
 {'name': 'pytest-playwright',
  'version': '0.10.0',
  'filename': 'pytest_playwright-0.10.0-py3-none-any.whl',
  'sha256': '8314d1af726e2c15531635902ece3ee47ed83f5a75c937a7eda8686d3dae6c0d',
  'license': 'Apache-2.0'},
 {'name': 'python-discovery',
  'version': '1.6.4',
  'filename': 'python_discovery-1.6.4-py3-none-any.whl',
  'sha256': '530179cc51a1816d512b15635b3dc931295ae12efb183783ad31190a5d425d2b',
  'license': 'MIT'},
 {'name': 'python-slugify',
  'version': '9.1.3',
  'filename': 'python_slugify-9.1.3-py3-none-any.whl',
  'sha256': '9aced0670e54c5603e2335c0fa9a4011ad4bc41ecb3c46e8097294c46fd60ed4',
  'license': 'MIT'},
 {'name': 'setuptools',
  'version': '84.2.1',
  'filename': 'setuptools-84.2.1-py3-none-any.whl',
  'sha256': 'ca140b45d5325a9478f880e351484f62fef15f336462e449ca0c03c873d589c2',
  'license': 'MIT'},
 {'name': 'text-unidecode',
  'version': '1.3',
  'filename': 'text_unidecode-1.3-py2.py3-none-any.whl',
  'sha256': '1311f10e8b895935241623731c2ba64f4c455287888b18189350b67134a822e8',
  'license': 'Artistic License'},
 {'name': 'typing_extensions',
  'version': '4.16.0',
  'filename': 'typing_extensions-4.16.0-py3-none-any.whl',
  'sha256': '481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8',
  'license': 'PSF-2.0'},
 {'name': 'virtualenv',
  'version': '21.14.12',
  'filename': 'virtualenv-21.14.12-py3-none-any.whl',
  'sha256': '7820aeaef23f1f59a96458edfc7f9d3deac937155718de15f1c9a64471e15551',
  'license': 'MIT'},
 {'name': 'wheel',
  'version': '0.48.0',
  'filename': 'wheel-0.48.0-py3-none-any.whl',
  'sha256': '3217dcc807155e45db462d7ef2431f5ddda0d7273b700d05a67b271ceb1287ab',
  'license': 'MIT'}]


def requirements(owned=None):
    lines = [f"{w['name']}=={w['version']} --hash=sha256:{w['sha256']}" for w in WHEELS]
    if owned is not None:
        wheels = list(Path(owned).glob('project_vandal-*.whl'))
        if len(wheels) != 1:
            raise ValueError('expected one built owned wheel')
        wheel = wheels[0]
        lines.append(f"{wheel} --hash=sha256:{hashlib.sha256(wheel.read_bytes()).hexdigest()}")
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--include-owned', type=Path)
    args = parser.parse_args()
    print(requirements(args.include_owned), end='')
