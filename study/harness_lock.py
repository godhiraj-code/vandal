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
  'license': 'Apache License\n'
             '                                   Version 2.0, January 2004\n'
             '                                http://www.apache.org/licenses/\n'
             '        \n'
             '           TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION\n'
             '        \n'
             '           1. Definitions.\n'
             '        \n'
             '              "License" shall mean the terms and conditions for use, reproduction,\n'
             '              and distribution as defined by Sections 1 through 9 of this document.\n'
             '        \n'
             '              "Licensor" shall mean the copyright owner or entity authorized by\n'
             '              the copyright owner that is granting the License.\n'
             '        \n'
             '              "Legal Entity" shall mean the union of the acting entity and all\n'
             '              other entities that control, are controlled by, or are under common\n'
             '              control with that entity. For the purposes of this definition,\n'
             '              "control" means (i) the power, direct or indirect, to cause the\n'
             '              direction or management of such entity, whether by contract or\n'
             '              otherwise, or (ii) ownership of fifty percent (50%) or more of the\n'
             '              outstanding shares, or (iii) beneficial ownership of such entity.\n'
             '        \n'
             '              "You" (or "Your") shall mean an individual or Legal Entity\n'
             '              exercising permissions granted by this License.\n'
             '        \n'
             '              "Source" form shall mean the preferred form for making modifications,\n'
             '              including but not limited to software source code, documentation\n'
             '              source, and configuration files.\n'
             '        \n'
             '              "Object" form shall mean any form resulting from mechanical\n'
             '              transformation or translation of a Source form, including but\n'
             '              not limited to compiled object code, generated documentation,\n'
             '              and conversions to other media types.\n'
             '        \n'
             '              "Work" shall mean the work of authorship, whether in Source or\n'
             '              Object form, made available under the License, as indicated by a\n'
             '              copyright notice that is included in or attached to the work\n'
             '              (an example is provided in the Appendix below).\n'
             '        \n'
             '              "Derivative Works" shall mean any work, whether in Source or Object\n'
             '              form, that is based on (or derived from) the Work and for which the\n'
             '              editorial revisions, annotations, elaborations, or other modifications\n'
             '              represent, as a whole, an original work of authorship. For the purposes\n'
             '              of this License, Derivative Works shall not include works that remain\n'
             '              separable from, or merely link (or bind by name) to the interfaces of,\n'
             '              the Work and Derivative Works thereof.\n'
             '        \n'
             '              "Contribution" shall mean any work of authorship, including\n'
             '              the original version of the Work and any modifications or additions\n'
             '              to that Work or Derivative Works thereof, that is intentionally\n'
             '              submitted to Licensor for inclusion in the Work by the copyright owner\n'
             '              or by an individual or Legal Entity authorized to submit on behalf of\n'
             '              the copyright owner. For the purposes of this definition, "submitted"\n'
             '              means any form of electronic, verbal, or written communication sent\n'
             '              to the Licensor or its representatives, including but not limited to\n'
             '              communication on electronic mailing lists, source code control systems,\n'
             '              and issue tracking systems that are managed by, or on behalf of, the\n'
             '              Licensor for the purpose of discussing and improving the Work, but\n'
             '              excluding communication that is conspicuously marked or otherwise\n'
             '              designated in writing by the copyright owner as "Not a Contribution."\n'
             '        \n'
             '              "Contributor" shall mean Licensor and any individual or Legal Entity\n'
             '              on behalf of whom a Contribution has been received by Licensor and\n'
             '              subsequently incorporated within the Work.\n'
             '        \n'
             '           2. Grant of Copyright License. Subject to the terms and conditions of\n'
             '              this License, each Contributor hereby grants to You a perpetual,\n'
             '              worldwide, non-exclusive, no-charge, royalty-free, irrevocable\n'
             '              copyright license to reproduce, prepare Derivative Works of,\n'
             '              publicly display, publicly perform, sublicense, and distribute the\n'
             '              Work and such Derivative Works in Source or Object form.\n'
             '        \n'
             '           3. Grant of Patent License. Subject to the terms and conditions of\n'
             '              this License, each Contributor hereby grants to You a perpetual,\n'
             '              worldwide, non-exclusive, no-charge, royalty-free, irrevocable\n'
             '              (except as stated in this section) patent license to make, have made,\n'
             '              use, offer to sell, sell, import, and otherwise transfer the Work,\n'
             '              where such license applies only to those patent claims licensable\n'
             '              by such Contributor that are necessarily infringed by their\n'
             '              Contribution(s) alone or by combination of their Contribution(s)\n'
             '              with the Work to which such Contribution(s) was submitted. If You\n'
             '              institute patent litigation against any entity (including a\n'
             '              cross-claim or counterclaim in a lawsuit) alleging that the Work\n'
             '              or a Contribution incorporated within the Work constitutes direct\n'
             '              or contributory patent infringement, then any patent licenses\n'
             '              granted to You under this License for that Work shall terminate\n'
             '              as of the date such litigation is filed.\n'
             '        \n'
             '           4. Redistribution. You may reproduce and distribute copies of the\n'
             '              Work or Derivative Works thereof in any medium, with or without\n'
             '              modifications, and in Source or Object form, provided that You\n'
             '              meet the following conditions:\n'
             '        \n'
             '              (a) You must give any other recipients of the Work or\n'
             '                  Derivative Works a copy of this License; and\n'
             '        \n'
             '              (b) You must cause any modified files to carry prominent notices\n'
             '                  stating that You changed the files; and\n'
             '        \n'
             '              (c) You must retain, in the Source form of any Derivative Works\n'
             '                  that You distribute, all copyright, patent, trademark, and\n'
             '                  attribution notices from the Source form of the Work,\n'
             '                  excluding those notices that do not pertain to any part of\n'
             '                  the Derivative Works; and\n'
             '        \n'
             '              (d) If the Work includes a "NOTICE" text file as part of its\n'
             '                  distribution, then any Derivative Works that You distribute must\n'
             '                  include a readable copy of the attribution notices contained\n'
             '                  within such NOTICE file, excluding those notices that do not\n'
             '                  pertain to any part of the Derivative Works, in at least one\n'
             '                  of the following places: within a NOTICE text file distributed\n'
             '                  as part of the Derivative Works; within the Source form or\n'
             '                  documentation, if provided along with the Derivative Works; or,\n'
             '                  within a display generated by the Derivative Works, if and\n'
             '                  wherever such third-party notices normally appear. The contents\n'
             '                  of the NOTICE file are for informational purposes only and\n'
             '                  do not modify the License. You may add Your own attribution\n'
             '                  notices within Derivative Works that You distribute, alongside\n'
             '                  or as an addendum to the NOTICE text from the Work, provided\n'
             '                  that such additional attribution notices cannot be construed\n'
             '                  as modifying the License.\n'
             '        \n'
             '              You may add Your own copyright statement to Your modifications and\n'
             '              may provide additional or different license terms and conditions\n'
             '              for use, reproduction, or distribution of Your modifications, or\n'
             '              for any such Derivative Works as a whole, provided Your use,\n'
             '              reproduction, and distribution of the Work otherwise complies with\n'
             '              the conditions stated in this License.\n'
             '        \n'
             '           5. Submission of Contributions. Unless You explicitly state otherwise,\n'
             '              any Contribution intentionally submitted for inclusion in the Work\n'
             '              by You to the Licensor shall be under the terms and conditions of\n'
             '              this License, without any additional terms or conditions.\n'
             '              Notwithstanding the above, nothing herein shall supersede or modify\n'
             '              the terms of any separate license agreement you may have executed\n'
             '              with Licensor regarding such Contributions.\n'
             '        \n'
             '           6. Trademarks. This License does not grant permission to use the trade\n'
             '              names, trademarks, service marks, or product names of the Licensor,\n'
             '              except as required for reasonable and customary use in describing the\n'
             '              origin of the Work and reproducing the content of the NOTICE file.\n'
             '        \n'
             '           7. Disclaimer of Warranty. Unless required by applicable law or\n'
             '              agreed to in writing, Licensor provides the Work (and each\n'
             '              Contributor provides its Contributions) on an "AS IS" BASIS,\n'
             '              WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or\n'
             '              implied, including, without limitation, any warranties or conditions\n'
             '              of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A\n'
             '              PARTICULAR PURPOSE. You are solely responsible for determining the\n'
             '              appropriateness of using or redistributing the Work and assume any\n'
             '              risks associated with Your exercise of permissions under this License.\n'
             '        \n'
             '           8. Limitation of Liability. In no event and under no legal theory,\n'
             '              whether in tort (including negligence), contract, or otherwise,\n'
             '              unless required by applicable law (such as deliberate and grossly\n'
             '              negligent acts) or agreed to in writing, shall any Contributor be\n'
             '              liable to You for damages, including any direct, indirect, special,\n'
             '              incidental, or consequential damages of any character arising as a\n'
             '              result of this License or out of the use or inability to use the\n'
             '              Work (including but not limited to damages for loss of goodwill,\n'
             '              work stoppage, computer failure or malfunction, or any and all\n'
             '              other commercial damages or losses), even if such Contributor\n'
             '              has been advised of the possibility of such damages.\n'
             '        \n'
             '           9. Accepting Warranty or Additional Liability. While redistributing\n'
             '              the Work or Derivative Works thereof, You may choose to offer,\n'
             '              and charge a fee for, acceptance of support, warranty, indemnity,\n'
             '              or other liability obligations and/or rights consistent with this\n'
             '              License. However, in accepting such obligations, You may act only\n'
             '              on Your own behalf and on Your sole responsibility, not on behalf\n'
             '              of any other Contributor, and only if You agree to indemnify,\n'
             '              defend, and hold each Contributor harmless for any liability\n'
             '              incurred by, or claims asserted against, such Contributor by reason\n'
             '              of your accepting any such warranty or additional liability.\n'
             '        \n'
             '           END OF TERMS AND CONDITIONS\n'
             '        \n'
             '           APPENDIX: How to apply the Apache License to your work.\n'
             '        \n'
             '              To apply the Apache License to your work, attach the following\n'
             '              boilerplate notice, with the fields enclosed by brackets "[]"\n'
             "              replaced with your own identifying information. (Don't include\n"
             '              the brackets!)  The text should be enclosed in the appropriate\n'
             '              comment syntax for the file format. We also recommend that a\n'
             '              file or class name and description of purpose be included on the\n'
             '              same "printed page" as the copyright notice for easier\n'
             '              identification within third-party archives.\n'
             '        \n'
             '           Portions Copyright (c) Microsoft Corporation.\n'
             '           Portions Copyright 2017 Google Inc.\n'
             '        \n'
             '           Licensed under the Apache License, Version 2.0 (the "License");\n'
             '           you may not use this file except in compliance with the License.\n'
             '           You may obtain a copy of the License at\n'
             '        \n'
             '               http://www.apache.org/licenses/LICENSE-2.0\n'
             '        \n'
             '           Unless required by applicable law or agreed to in writing, software\n'
             '           distributed under the License is distributed on an "AS IS" BASIS,\n'
             '           WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n'
             '           See the License for the specific language governing permissions and\n'
             '           limitations under the License.\n'
             '        '},
 {'name': 'python-discovery',
  'version': '1.6.4',
  'filename': 'python_discovery-1.6.4-py3-none-any.whl',
  'sha256': '530179cc51a1816d512b15635b3dc931295ae12efb183783ad31190a5d425d2b',
  'license': 'Permission is hereby granted, free of charge, to any person obtaining a\n'
             '        copy of this software and associated documentation files (the\n'
             '        "Software"), to deal in the Software without restriction, including\n'
             '        without limitation the rights to use, copy, modify, merge, publish,\n'
             '        distribute, sublicense, and/or sell copies of the Software, and to\n'
             '        permit persons to whom the Software is furnished to do so, subject to\n'
             '        the following conditions:\n'
             '        \n'
             '        The above copyright notice and this permission notice shall be included\n'
             '        in all copies or substantial portions of the Software.\n'
             '        \n'
             '        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS\n'
             '        OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF\n'
             '        MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.\n'
             '        IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY\n'
             '        CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,\n'
             '        TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE\n'
             '        SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.'},
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
