cat > ~/.pypirc <<EOF
[distutils]
index-servers =
  pypi
  pypitest

[pypi]
username=qwer
password=asdf

[pypitest]
repository: https://test.pypi.org/legacy/
username=qwer
password=asdf
EOF


# set pypi password
chmod 600 ~/.pypirc
sed -ri 's/qwer/username/;s/asdf/password/' ~/.pypirc

# setup build env
cd ~/dev/r0c &&
virtualenv buildenv

# build and release
function have() { python -c "import $1; $1; $1.__version__"; }
deactivate;
cd ~/dev/r0c &&
rm -rf dist r0c.egg-info/ build/ MANIFEST* &&
. buildenv/bin/activate &&
have setuptools &&
have wheel &&
have m2r &&
./setup.py clean2 &&
./setup.py rstconv &&
./setup.py sdist bdist_wheel --universal &&
./setup.py sdist upload -r pypi &&
deactivate &&
echo all done
