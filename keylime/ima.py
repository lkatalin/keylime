'''
SPDX-License-Identifier: Apache-2.0
Copyright 2017 Massachusetts Institute of Technology.
'''

import ast
import codecs
import hashlib
import struct
import os

from keylime import config
from keylime import keylime_logging

logger = keylime_logging.init_logging('ima')

#         m = ima_measure_re.match(measure_line)
#         measure  = m.group('file_hash')
#         filename = m.group('file_path')

START_HASH = (codecs.decode('0000000000000000000000000000000000000000', 'hex'))
FF_HASH = (codecs.decode('ffffffffffffffffffffffffffffffffffffffff', 'hex'))


# struct event {
#     struct {
#         u_int32_t pcr;
#         u_int8_t digest[SHA_DIGEST_LENGTH];
#         u_int32_t name_len;
#     } header;
#     char name[TCG_EVENT_NAME_LEN_MAX + 1];
#     struct ima_template_desc *template_desc; /* template descriptor */
#     u_int32_t template_data_len;
#     u_int8_t *template_data;    /* template related data */
# };


def read_unpack(fd, fmt):
    return struct.unpack(fmt, fd.read(struct.calcsize(fmt)))


TCG_EVENT_NAME_LEN_MAX = 255
SHA_DIGEST_LEN = 20

defined_templates = {
    'ima': 'd|n',
    'ima-ng': 'd-ng|n-ng',
    'ima-sig': 'd-ng|n-ng|sig;',
}


def ima_eventname_parse():
    pass


def ima_eventdigest_ng_parse():
    pass


def ima_eventname_ng_parse():
    pass


def ima_eventsig_parse():
    pass


supported_fields = {
    "n": ima_eventname_parse,
    "d-ng": ima_eventdigest_ng_parse,
    "n-ng": ima_eventname_ng_parse,
    "sig": ima_eventsig_parse,
}


def read_measurement_list_bin(path):
    raise Exception("not implementated fully yet")
    # pylint: disable=W0101
    f = open(path, 'rb')

    while True:
        template = {}
        (template['pcr'], template['digest'],
         template['name_len']) = read_unpack(f, "<I20sI")

        if template['name_len'] > TCG_EVENT_NAME_LEN_MAX:
            raise Exception("Error event name too long: %d" %
                            template['name_len'])

        name = read_unpack(f, "<%ds" % template['name_len'])[0]

        is_ima_template = name == 'ima'
        if not is_ima_template:
            template['data_len'] = read_unpack(f, "<I")[0]
            print("reading ima len %d" % template['data_len'])
        else:
            template['data_len'] = SHA_DIGEST_LEN + TCG_EVENT_NAME_LEN_MAX + 1

        template['data'] = read_unpack(f, "<%ds" % template['data_len'])[0]

        if is_ima_template:
            field_len = read_unpack(f, "<I")[0]
            extra_data = read_unpack(f, "<%ds" % field_len)[0]
            template['data'] += extra_data

        print("record %s" % template)

        if template['name'] not in list(defined_templates.keys()):
            template['name'] = 'ima'
        template['desc-fmt'] = defined_templates[template['name']]

        # tokens = template['desc-fmt'].split('|')


def _extract_from_ima(tokens, template_hash):
    """ Extract filedata_hash & path form 'ima' entry; return 1 in case error occurred """
    filedata_hash = codecs.decode(tokens[3], "hex")
    path = str(tokens[4])

    # this is some IMA weirdness
    if template_hash == START_HASH:
        return filedata_hash, path, 0

    # verify template hash. yep this is terrible
    # name needs to be null padded out to MAX len. +1 is for the null terminator of the string itself
    fmt = "<%ds%ds%ds" % (len(filedata_hash), len(path), TCG_EVENT_NAME_LEN_MAX - len(path) + 1)
    tohash = struct.pack(fmt,
                         filedata_hash, path.encode("utf-8"),
                         bytearray(TCG_EVENT_NAME_LEN_MAX - len(path) + 1))
    expected_template_hash = hashlib.sha1(tohash).digest()

    if expected_template_hash != template_hash:
        error = 1
        logger.warning("template hash for file %s does not match %s != %s" %
                       (path,
                        codecs.encode(expected_template_hash, 'hex').decode('utf-8'),
                        codecs.encode(template_hash, 'hex').decode('utf-8')))
    else:
        error = 0

    return filedata_hash, path, error


def _extract_from_ima_ng(tokens, template_hash):
    """ Extract filedata_hash & path form 'ima-ng' entry; return 1 in case error occurred """
    filedata = tokens[3]
    ftokens = filedata.split(":")
    filedata_hash = codecs.decode(ftokens[1], 'hex')
    path = str(tokens[4])

    # this is some IMA weirdness
    if template_hash == START_HASH:
        return filedata_hash, path, 0

    filedata_algo = str(ftokens[0])
    # verify template hash. yep this is terrible
    fmt = "<I%dsBB%dsI%dsB" % (len(filedata_algo), len(filedata_hash), len(path))
    # +2 for the : and the null terminator, and +1 on path for null terminator
    tohash = struct.pack(fmt,
                         len(filedata_hash) + len(filedata_algo) + 2,
                         filedata_algo.encode('utf-8'), ord(':'), ord('\0'),
                         filedata_hash,
                         len(path) + 1,
                         path.encode("utf-8"),
                         ord('\0'))
    expected_template_hash = hashlib.sha1(tohash).digest()

    if expected_template_hash != template_hash:
        error = 1
        logger.warning("template hash for file %s does not match %s != %s" %
                       (path,
                        codecs.encode(expected_template_hash, 'hex').decode('utf-8'),
                        codecs.encode(template_hash, 'hex').decode('utf-8')))
    else:
        error = 0

    return filedata_hash, path, error


def _extract_from_ima_sig(tokens, template_hash):
    """ Extract filedata_hash & path form 'ima-sig' entry; return 1 in case error occurred """
    filedata = tokens[3]
    ftokens = filedata.split(":")
    filedata_hash = codecs.decode(ftokens[1], 'hex')
    path = str(tokens[4])

    # this is some IMA weirdness
    if template_hash == START_HASH:
        return filedata_hash, path, None, None, 0

    filedata_algo = str(ftokens[0])
    # verify template hash. yep this is terrible
    fmt = "<I%dsBB%dsI%dsB" % (len(filedata_algo), len(filedata_hash), len(path))
    # +2 for the : and the null terminator, and +1 on path for null terminator
    tohash = struct.pack(fmt,
                         len(filedata_hash) + len(filedata_algo) + 2,
                         filedata_algo.encode('utf-8'), ord(':'), ord('\0'),
                         filedata_hash,
                         len(path) + 1,
                         path.encode("utf-8"),
                         ord('\0'))
    signature = b''
    if len(tokens) == 6:
        signature = codecs.decode(tokens[5], 'hex')
    tohash += struct.pack("<I%ds" % len(signature), len(signature), signature)
    expected_template_hash = hashlib.sha1(tohash).digest()

    if expected_template_hash != template_hash:
        error = 1
        logger.warning("template hash for file %s does not match %s != %s" %
                       (path,
                        codecs.encode(expected_template_hash, 'hex').decode('utf-8'),
                        codecs.encode(template_hash, 'hex').decode('utf-8')))
    else:
        error = 0

    return filedata_hash, path, signature, filedata_algo, error


def process_measurement_list(lines, lists=None, m2w=None, pcrval=None, ima_keyring=None):
    errs = [0, 0, 0, 0, 0]
    runninghash = START_HASH
    found_pcr = (pcrval is None)

    if lists is not None:
        lists = ast.literal_eval(lists)
        allowlist = lists['allowlist']
        exclude_list = lists['exclude']
    else:
        allowlist = None
        exclude_list = None

    is_valid, compiled_regex, err_msg = config.valid_exclude_list(exclude_list)
    if not is_valid:
        # This should not happen as the exclude list has already been validated
        # by the verifier before acceping it. This is a safety net just in case.
        err_msg += " Exclude list will be ignored."
        logger.error(err_msg)

    for line in lines:
        line = line.strip()
        if line == '':
            continue

        tokens = line.split(None, 5)
        if len(tokens) < 5 or len(tokens) > 6:
            logger.error("invalid measurement list file line: -%s-" % (line))
            return None

        # print tokens
        # pcr = tokens[0]
        template_hash = codecs.decode(tokens[1], 'hex')
        mode = tokens[2]
        signature = None
        filedata_algo = None

        if mode == "ima-ng":
            filedata_hash, path, error = _extract_from_ima_ng(tokens,
                                                              template_hash)
        elif mode == "ima-sig":
            filedata_hash, path, signature, filedata_algo, error = \
                _extract_from_ima_sig(tokens, template_hash)
        elif mode == 'ima':
            filedata_hash, path, error = _extract_from_ima(tokens,
                                                           template_hash)
        else:
            raise Exception("unsupported ima template mode: %s" % mode)

        errs[0] += error
        if template_hash == START_HASH:
            template_hash = FF_HASH

        # update hash
        runninghash = hashlib.sha1(runninghash + template_hash).digest()

        if not found_pcr:
            found_pcr = \
                (codecs.encode(runninghash, 'hex').decode('utf-8') == pcrval)

        # write out the new hash
        if m2w is not None:
            m2w.write("%s %s\n" %
                      (codecs.encode(filedata_hash, 'hex').decode('utf-8'),
                       path))

        evaluated = False

        if signature and ima_keyring:
            evaluated = True
            # determine if path matches any exclusion list items
            if compiled_regex is not None and compiled_regex.match(path):
                logger.debug("IMA: ignoring excluded path %s" % path)
                continue

            if not ima_keyring.integrity_digsig_verify(signature, filedata_hash, filedata_algo):
                logger.warning("signature for file %s is not valid" % (path))
                errs[3] += 1
            else:
                logger.debug("signature for file %s is good" % path)

        if allowlist is not None:
            # just skip if it is a weird overwritten path
            if template_hash == FF_HASH:
                # print "excluding ffhash %s"%path
                continue

            # determine if path matches any exclusion list items
            if compiled_regex is not None and compiled_regex.match(path):
                logger.debug("IMA: ignoring excluded path %s" % path)
                continue

            accept_list = allowlist.get(path, None)
            if accept_list is None:
                # if it's NOT already evaluated by a file signature then a
                # missing file entry is an error -- this enforces that every
                # entry is 'covered' by signature or allowlist
                if not evaluated:
                    logger.warning("File not found in allowlist: %s" % (path))
                    errs[1] += 1
                continue

            # print('codecs.encode', codecs.encode(filedata_hash, 'hex').decode('utf-8'))
            # print('accept_list:', accept_list)
            if codecs.encode(filedata_hash, 'hex').decode('utf-8') not in accept_list:
                logger.warning("Hashes for file %s don't match %s not in %s" %
                               (path,
                                codecs.encode(filedata_hash, 'hex').decode('utf-8'),
                                accept_list))
                errs[2] += 1
                continue

            evaluated = True

        if ima_keyring and not evaluated:
            logger.warning("File %s not evaluated with signature or allowlist" % path)
            errs[1] += 1

        errs[4] += 1

    # check PCR value has been found
    if not found_pcr:
        logger.error("IMA measurement list does not match TPM PCR %s" % pcrval)
        return None

    # clobber the retval if there were IMA file errors
    if sum(errs[:4]) > 0:
        logger.error(
            "IMA ERRORS: template-hash %d fnf %d hash %d bad-sig %d good %d" % tuple(errs))
        return None

    return codecs.encode(runninghash, 'hex').decode('utf-8')


def process_allowlists(al_data, excl_data):
    # Pull in default config values if not specified
    if al_data is None:
        al_data = read_allowlist()
    if excl_data is None:
        excl_data = read_excllist()

    allowlist = {}
    for line in al_data:
        line = line.strip()
        tokens = line.split(None, 1)
        if len(tokens) != 2:
            continue
        fhash = tokens[0]
        path = str(tokens[1])
        tmp = allowlist.get(path, [])
        tmp.append(fhash)
        allowlist[path] = tmp

    if allowlist.get('boot_aggregate', None) is None:
        logger.warning(
            "No boot_aggregate value found in allowlist, adding an empty one")
        allowlist['boot_aggregate'] = [
            '0000000000000000000000000000000000000000']

    for excl in excl_data:
        if excl.startswith("#"):
            excl_data.remove(excl)
        # don't allow empty lines in exclude list, it will match everything
        if excl == "":
            excl_data.remove(excl)

    return{'allowlist': allowlist, 'exclude': excl_data}


def read_allowlist(al_path=None):
    if al_path is None:
        al_path = config.get('tenant', 'ima_allowlist')
        if config.STUB_IMA:
            al_path = '../scripts/ima/allowlist.txt'

    # If user only wants signatures then an allowlist is not required
    if al_path is None or al_path == '':
        return []

    # Purposefully die if path doesn't exist
    with open(al_path, 'r') as f:
        alist = f.read()
    alist = alist.splitlines()

    logger.debug("Loaded allowlist from %s" % (al_path))

    return alist


def read_excllist(exclude_path=None):
    if exclude_path is None:
        exclude_path = config.get('tenant', 'ima_excludelist')
        if config.STUB_IMA:
            exclude_path = '../scripts/ima/exclude.txt'

    excl_list = []
    if os.path.exists(exclude_path):
        with open(exclude_path, 'r') as f:
            excl_list = f.read()
        excl_list = excl_list.splitlines()

        logger.debug("Loaded exclusion list from %s: %s" %
                     (exclude_path, excl_list))

    return excl_list


def main():
    # read_measurement_list_bin("/sys/kernel/security/ima/binary_runtime_measurements")

    allowlist_path = 'allowlist.txt'
    print("reading allowlist from %s" % allowlist_path)

    exclude_path = 'exclude.txt'
    # exclude_path = '../scripts/ima/exclude.txt'
    print("reading exclude list from %s" % exclude_path)

    al_data = read_allowlist(allowlist_path)
    excl_data = read_excllist(exclude_path)
    lists = process_allowlists(al_data, excl_data)

    measure_path = config.IMA_ML
    # measure_path='../scripts/ima/ascii_runtime_measurements_ima'
    # measure_path = '../scripts/gerardo/ascii_runtime_measurements'
    print("reading measurement list from %s" % measure_path)
    f = open(measure_path, 'r')
    lines = f.readlines()

    m2a = open('measure2allow.txt', "w")
    digest = process_measurement_list(lines, lists, m2a)
    print("final digest is %s" % digest)
    f.close()
    m2a.close()

    print("using m2a")

    al_data = read_allowlist('measure2allow.txt')
    excl_data = read_excllist(exclude_path)
    lists2 = process_allowlists(al_data, excl_data)
    process_measurement_list(lines, lists2)

    print("done")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception(e)
