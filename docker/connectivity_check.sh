#!/bin/sh

# Run a few connectivity checks
echo "Checking external connectivity..."

CCTEMP=`mktemp -d`
cd $CCTEMP || exit 1

cleanup_tmp() {
    cd /tmp
    rm -rf $CCTEMP
}

HTTP_TEST_URL="http://example.com"
if ! wget -q $HTTP_TEST_URL ; then
    echo "ERROR: failed to fetch $HTTP_TEST_URL"
    cleanup_tmp
    exit 1
fi

HTTPS_TEST_URL="https://google.com"
if ! wget -q $HTTPS_TEST_URL ; then
    echo "ERROR: failed to fetch $HTTPS_TEST_URL"
    cleanup_tmp
    exit 1
fi

GIT_TEST_REPO="git://git.yoctoproject.org/meta-layerindex-test"
if ! git clone -q $GIT_TEST_REPO ; then
    echo "ERROR: failed to clone $GIT_TEST_REPO"
    cleanup_tmp
    exit 1
fi

cleanup_tmp
