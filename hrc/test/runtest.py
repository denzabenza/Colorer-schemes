"""\
Automatic HRC changes tests runner.
Validates parsing result for a set of source files against
previously collected data.

Advantage over Perl version:
- doesn't require diff utility
- works out of the box on Windows with Python installed

placed in public domain by techtonik // rainforce.org
"""

import sys
if sys.version_info < (3, 0):
    sys.stdout.write("Sorry, requires Python 3.x, not Python 2.x\n")
    sys.exit(1)

import os
import copy
import difflib
import optparse
import subprocess
import fnmatch
import multiprocessing.pool
from datetime import datetime
from os.path import dirname, join, normpath


# -- path setup --
tests_path = normpath(dirname(__file__))
root_path = join(tests_path, "..", "..")
with open(join(root_path, "path.properties")) as pf:
  prop_path = dict(
    [[x.strip()
      for x in line.strip()[5:].split("=")]
        for line in pf
          if line.startswith("path.")]
  )
# print(prop_path)

colorer_path = join(root_path, normpath(prop_path["colorer"]))
catalog_path = join(root_path, normpath(prop_path["catalog"]))
hrd_path     = join(root_path, normpath(prop_path["build-dir"]), prop_path["base-dir"], prop_path["hrd"])
hrd = os.getenv('COLORER5HRD', 'white')
css = "%s/css/%s.css" % (hrd_path, hrd)
if not os.path.isfile(css):
  print("Warning: Stylesheet %s does not exist" % css)

colorer_exe = "colorer"
colorer = join(colorer_path, colorer_exe)
if not os.path.isfile(colorer):
  sys.exit("Error: No %s in %s" % (colorer_exe, colorer_path))

colorer_opts = ["-c", catalog_path, "-eh", join(colorer_path, "error.log")]

valid_dir = normpath(join(tests_path, "_valid"))
# __2009-06-05_12-35-00
current_dir = datetime.today().strftime("__%Y-%m-%d_%H-%M-%S")
if os.path.exists(current_dir):
  sys.exit("Exiting: Test dir already exists - %s" % current_dir)
os.mkdir(current_dir)


# -- args parsing --

usage = "%prog [--quick] [GLOB...]"

opt = optparse.OptionParser(usage=usage, add_help_option=False)
opt.add_option("--quick", action="store_true", help="exclude /full/ dirs from testing")
opt.add_option("--help", action="store_true")
#opt.add_option("--list", action="store_true")
(options, args) = opt.parse_args()

if options.help:
  print(__doc__)
  opt.print_help()
  sys.exit(0)


# -- utility functions

def filediff(oldpath, newpath):
  """return diff output or empty string"""
  with open(oldpath, "r", errors="surrogateescape") as of:
    ol = of.readlines()
  with open(newpath, "r", errors="surrogateescape") as nf:
    nl = nf.readlines()
  diff = difflib.unified_diff(ol, nl, oldpath, newpath, n=1)
  return list(diff)


print("Running tests")

fail_log = open(join(current_dir, "fails.html"), "w")
fail_log.write(
"""
<html>
<head>
  <title>%s Colorer Test Results</title>
  <link href="%s" rel="stylesheet" type="text/css"/>
</head>
<body>
""" % (current_dir, normpath("../" + css)))
  

test_list = []
# look for files for highlight tests
# skip dirs: current ".", ".svn", "_valid" and "__*" results
for root, dirs, files in os.walk(tests_path):
  for d in copy.copy(dirs):
    if d[0] in (".", "_"):
      dirs.remove(d)
  if options.quick:
    if "full" in dirs:
      dirs.remove("full")
  if root == tests_path:
    continue
  for name in files:
    path = normpath(join(root, name))
    if len(args):
      for glob in args:
        if fnmatch.fnmatch(path, glob):
          break
      else:
        continue # next file
    test_list.append(path)

failed = 0
changed = 0
no = 0
total = len(test_list)

import threading
lock = threading.Lock()

def run_one_test(test):
  global no
  with lock:
    no += 1
    print("Processing (%s/%s) %s" % (no, len(test_list), test))

  filename = "%s.html" % test
  origname = join(  valid_dir, filename)
  outname  = join(current_dir, filename)
  outdir = dirname(outname)

  if not os.path.exists(outdir):
    #print(outdir)
    os.makedirs(outdir, exist_ok=True)

  args = ["-ht", test, "-dc", "-dh", "-ln", "-o", outname]
  cmd = [colorer] + colorer_opts + args
  # print(cmd)
  ret = subprocess.call(cmd)
  return (test, ret, origname, outname)

pool = multiprocessing.pool.ThreadPool()
results = pool.map(run_one_test, test_list)

print("Generating report...")
for test, ret, origname, outname in results:
  fail_log.write('<div><pre class="testname">%s</pre><pre>' % test)

  if ret != 0:
    failed += 1
    print("Failed: colorer returned %s" % ret)
    fail_log.write("Failed: colorer returned %s" % ret)
    # BUG: colorer doesn't return any error codes in some error cases
    #      like absent hrd catalogs or 
    fail_log.write('</pre></div>')
    continue

  # XXX: colorer.exe compiled with MinGW produces output with unix line ends
  #      but SVN checkout is made with unix ones. Converting lineends here
  #      until it's clear which lineends are generated by VS compiled version.
  if os.name == 'nt':
    with open(outname) as fr:
      lines = fr.readlines()
    with open(outname, "wb") as fw:
      fw.writelines(lines)

  if os.path.isfile(origname):
    diff = filediff(origname, outname)
    if len(diff):
      changed += 1
      for line in diff:
        fail_log.write(line)
  else:
    fail_log.write(origname + "does not exist!")
    changed += 1

  fail_log.write('</pre></div>')

fail_log.write('</body></html>')
fail_log.close()
print("Executed: %s, Failed: %s (%1.2f%%), Changed: %s (%1.2f%%)" % (len(test_list),
  failed , (float(failed )/len(test_list)*100),
  changed, (float(changed)/len(test_list)*100),
))


"""
# TODO / comments
# tune unittest differ to be 
# my $diff  = 'diff -U 1 -bB';

evaluate usefulness
 --full   - test all (default)
 --list   - test listed dirs
 file.lst - test list from file(s)

add timings

list types and detect which are not covered by tests

provide code coverage stats

"""
