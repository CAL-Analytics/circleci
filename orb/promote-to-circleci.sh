#!/bin/bash

unset $FORCE

[ -z "$2" ] && { echo "Usage: promote_to-circleci.sh ORB_NAME SEMVER <force: deletes existing tag>"; exit ; }
[ -z "$3" ] || FORCE=true

SEM_VER=$2
ORB_NAME=$1

echo "*** Generating b64 files ***"
for i in `find . -name "*.py" -not -path "*/venv/*"`; do cat $i | base64 > $i.b64; done
for i in `find src/scripts/bin -type f -not -path "*/venv/*" -not -name "*.b64"`; do cat $i | base64 > $i.b64; done

echo "*** Packing Orb into tmp.yml ***"
circleci orb pack src >tmp.yml

echo "*** Validating Orb from tmp.yml ***"
circleci orb validate tmp.yml

if [ "$?" != "0" ]; then
    echo "*** Orb validation failed. Debug and Manually remove the tmp.yml file ***"
    exit
fi

echo "*** Checking if tag exists ***"
TAG_EXISTS=$(git tag | grep v$SEM_VER)
[ ! -z "$TAG_EXISTS" ] && { 
    echo "*** Tag v$SEM_VER exists ***"
    if [ ! -z "$FORCE" ]; then
        echo "*** Force enabled, deleting tag. WARNING: This could break idempotency for orb ***"
        git push --delete origin v$SEM_VER
        git tag -d v$SEM_VER
    else
        echo "*** Exiting without deleting tag. Re-run with force enabled or change tag number ***"
        exit
    fi
}

echo "*** Tagging v$SEM_VER for new orb ***"
git tag -a v$SEM_VER -m "tagging for orb"

echo "*** Pushing tag to origin ***"
git push origin v$SEM_VER

echo "*** Publishing Orb with version v$SEM_VER ***"
circleci orb publish tmp.yml "${ORB_NAME}@${SEM_VER}"

echo "*** Cleaning up tmp.yml file ***"
rm -f tmp.yml
