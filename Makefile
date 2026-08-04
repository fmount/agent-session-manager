PREFIX   ?= $(HOME)/.local
BINDIR   := $(PREFIX)/bin
LIBDIR   := $(PREFIX)/lib/csm
CONFDIR  := $(HOME)/.config/csm

.PHONY: help install uninstall check test

help:
	@echo "csm — Agent Session Manager"
	@echo ""
	@echo "  make install     Install csm to $(BINDIR)"
	@echo "  make uninstall   Remove csm from $(BINDIR)"
	@echo "  make check       Verify runtime dependencies"
	@echo "  make test        Dry-run: list sessions without fzf"

check:
	@echo "Checking dependencies..."
	@command -v python3 >/dev/null 2>&1 \
		&& echo "  python3: $$(python3 --version 2>&1)" \
		|| { echo "  python3: MISSING (required)"; exit 1; }
	@command -v fzf >/dev/null 2>&1 \
		&& echo "  fzf:     $$(fzf --version 2>&1 | head -1)" \
		|| echo "  fzf:     not found (required for interactive mode)"
	@command -v claude >/dev/null 2>&1 \
		&& echo "  claude:  $$(claude --version 2>&1 | head -1)" \
		|| echo "  claude:  not found (required to resume sessions)"
	@test -d "$(HOME)/.claude/projects" \
		&& echo "  sessions: $$(find $(HOME)/.claude/projects -name '*.jsonl' | wc -l) session files found" \
		|| echo "  sessions: no project directory found"

install: check
	@mkdir -p $(BINDIR) $(LIBDIR) $(CONFDIR)
	install -m 755 csm $(LIBDIR)/csm
	install -m 644 util.py $(LIBDIR)/util.py
	install -m 644 pricing.py $(LIBDIR)/pricing.py
	@test -f $(CONFDIR)/config.json \
		&& echo "Config already exists at $(CONFDIR)/config.json — skipping" \
		|| { install -m 644 config.json $(CONFDIR)/config.json; echo "Installed default config to $(CONFDIR)/config.json"; }
	ln -sf $(LIBDIR)/csm $(BINDIR)/csm
	@echo ""
	@echo "Installed to $(LIBDIR)/, linked $(BINDIR)/csm"
	@echo "Make sure $(BINDIR) is in your PATH."

uninstall:
	rm -f $(BINDIR)/csm
	rm -rf $(LIBDIR)
	@echo "Removed $(BINDIR)/csm and $(LIBDIR)/"
	@echo "Config left in $(CONFDIR)/ — remove manually if desired."

test:
	./csm --list -n 10
