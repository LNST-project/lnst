from lnst.Common.ExecCmd import exec_cmd

class FirewallControl(object):
    def _extract_tables_n_chains(self, ruleset):
        out = {}
        curtable = None
        for line in ruleset.split('\n'):
            if len(line.strip()) == 0:
                continue
            if line[0] == '*':
                curtable = line[1:]
                out[curtable] = []
            elif line[0] == ':':
                words = line.split(' ')
                if not words[1] == '-': # ignore user-defined chains
                    out[curtable].append(words[0][1:])
        return out

    def _append_missing_parts(self, dst_ruleset, src_ruleset):
        for table, chains in self._extract_tables_n_chains(src_ruleset).items():
            tline = f'*{table}\n'
            if dst_ruleset.find(tline) >= 0:
                continue
            dst_ruleset += tline
            for chain in chains:
                dst_ruleset += f':{chain} ACCEPT [0:0]\n'
            dst_ruleset += 'COMMIT\n'
        return dst_ruleset

    def apply_nftables_ruleset(self, ruleset):
        ruleset = f"flush ruleset\n{ruleset.decode('utf-8')}"
        old, err = exec_cmd("nft list ruleset",
                            report_stderr=True, log_outputs=False)
        exec_cmd("nft -f -", report_stderr=True,
                 stdin=ruleset.encode('utf-8'))
        return old.encode('utf-8')

    def apply_iptableslike_ruleset(self, cmd, ruleset):
        ruleset = ruleset.decode('utf-8')
        cmd = cmd.decode('utf-8')
        old, err = exec_cmd(f"{cmd}-save --counters",
                            report_stderr=True, log_outputs=False)
        ruleset = self._append_missing_parts(ruleset, old)
        exec_cmd(f"{cmd}-restore --counters", report_stderr=True,
                 stdin=ruleset.encode('utf-8'))
        return old.encode('utf-8')
