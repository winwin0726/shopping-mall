"""Record of an unsuccessful decompilation attempt.

The original file was UTF-16 text containing only uncompyle6 metadata and an
"Unsupported Python version" message. It is intentionally kept as a valid
Python module so broad compile/build checks do not fail on an artifact that is
not part of the runtime.
"""
