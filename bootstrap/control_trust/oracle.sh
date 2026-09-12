#!/bin/sh
# The F0 primitive process oracle: a second, INDEPENDENT observer of one pytest
# subject. POSIX shell on purpose -- it shares no library, parser or serializer
# with the candidate whose receipt it is compared against, so the two cannot
# agree by construction.
#
# CONTRACT: oracle.sh --target T --workroot W --nonce N --python P
#           --pycache-prefix D  ->  one flat f0-oracle-1 record on stdout.
#
# There is deliberately NO --output argument: the private path the harness saves
# this record to is never named here, so it can never be handed to the candidate.
# No product decision vocabulary is emitted and no product state is written.
#
# `set -u` is NOT used: bash 3.2, which is macOS /bin/sh, treats "$@" with no
# positional parameters as an unbound variable, and the run arm below calls
# measure() with none.

target=''
workroot=''
nonce=''
python=''
pycache=''

while [ $# -gt 0 ]; do
    if [ $# -lt 2 ]; then
        printf 'oracle.sh: %s has no value\n' "$1" >&2
        exit 2
    fi
    case $1 in
        --target) target=$2 ;;
        --workroot) workroot=$2 ;;
        --nonce) nonce=$2 ;;
        --python) python=$2 ;;
        --pycache-prefix) pycache=$2 ;;
        *)
            printf 'oracle.sh: unknown option %s\n' "$1" >&2
            exit 2
            ;;
    esac
    shift 2
done

if [ -z "$target" ] || [ -z "$workroot" ] || [ -z "$nonce" ] ||
    [ -z "$python" ] || [ -z "$pycache" ]; then
    printf 'oracle.sh: target/workroot/nonce/python/pycache-prefix are required\n' >&2
    exit 2
fi
if [ ! -f "$target" ]; then
    printf 'oracle.sh: no subject at %s\n' "$target" >&2
    exit 2
fi

# ONE pytest invocation site. Each measurement flag therefore occurs exactly
# once in this file, so a mutant that removes the conftest suppression cannot
# leave the run arm accidentally protected, and an anchored substitution cannot
# silently hit a second copy. Every path is quoted: a workroot containing a
# space is a real case here.
measure() {
    "$python" -B -X "pycache_prefix=$pycache" -I -m pytest \
        -p no:cacheprovider -c /dev/null --rootdir="$workroot" \
        --noconftest "$@" -q "$target"
}

# The child's status is saved IMMEDIATELY, before any parsing, sorting or
# formatting can overwrite $?. Nothing is piped into these two lines: a pipeline
# reports its LAST stage's status, which is how a real failure gets lost.
collect_out=$(measure --collect-only)
collect_exit=$?
measure >/dev/null 2>&1
run_exit=$?

python_version=$("$python" -B -I -c 'import platform;print(platform.python_version())')
subject_digest=$("$python" -B -I -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$target")

# STRICT, and it fails CLOSED: the part before `::` must be whitespace-free and
# end in .py, so a rootdir misconfiguration yields a visible EMPTY selection
# rather than plausible ids that identify no file. Anything after `::` is kept,
# because `test_alpha[with space]` is a real parameter id and dropping it loses a
# selected node while the count still looks healthy. Sorting is part of the
# compared fact: an unsorted list makes two honest runs disagree.
selected=$(printf '%s\n' "$collect_out" |
    sed -n 's/^\([^ :][^ ]*\.py::.*\)$/\1/p' |
    LC_ALL=C sort)

if [ -n "$selected" ]; then
    selected_count=$(printf '%s\n' "$selected" | wc -l | tr -cd '0-9')
else
    selected_count=0
fi

# ONE record on stdout, whose values are never re-parsed from anything this
# script already printed. It is NOT emitted atomically: the record leaves this
# script through several printf calls plus the sed that prefixes the selection,
# so a reader that sees a truncated record must treat it as ABSENT evidence
# rather than as agreement -- which is exactly what the comparator's
# ORACLE_EMPTY and ORACLE_MALFORMED arms do. No store, lock or persistence
# algorithm is introduced here to make it atomic; the reader owns that.
# A value may contain spaces: a parameter node id and a workroot path both do,
# so nothing here is word-split or quoted away.
printf 'schema=%s\npython=%s\npython_version=%s\ntarget=%s\nsubject_digest=%s\ncollect_exit=%s\nrun_exit=%s\nselected_count=%s\nnonce=%s\n' \
    'f0-oracle-1' "$python" "$python_version" "$target" "$subject_digest" \
    "$collect_exit" "$run_exit" "$selected_count" "$nonce"
if [ -n "$selected" ]; then
    printf '%s\n' "$selected" | sed 's/^/selected=/'
fi
exit 0
