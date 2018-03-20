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
deactivate;
cd ~/dev/r0c &&
rm -rf dist r0c.egg-info/ build/ MANIFEST* &&
. buildenv/bin/activate &&
python -c 'import setuptools; setuptools; setuptools.__version__' &&
python -c 'import wheel; wheel; wheel.__version__' &&
./setup.py sdist bdist_wheel --universal &&
./setup.py sdist upload -r pypi &&
deactivate &&
echo all done
