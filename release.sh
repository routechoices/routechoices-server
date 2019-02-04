#!/bin/sh
set -e

find_free_tag() {
    today=v$(date '+%Y%m%d')

    for seq in $(seq --format "%02g" 0 99); do
        new_tag=$today$seq
        git tag | grep -q "^$new_tag\$" || break
    done

    echo $new_tag
}

tag=$(find_free_tag)
echo "Found free tag: $tag"

# Sanity checks
if ! (git status -sb CHANGELOG.md | grep -q "^ M"); then
    echo -n "git says CHANGELOG.md has not been modified. Add release info for "
    echo "$tag and try again."
    exit 1
fi

if ! grep -q "^$tag" CHANGELOG.md; then
    echo "$tag not found in CHANGELOG.md!"
    exit 1
fi

git commit CHANGELOG.md -m "$tag"
git tag -s -m "$tag" "$tag"
echo
echo
echo "Done. Now run:"
echo "git push origin master --tags"
