PREFIX   ?= $(HOME)/.local
BINDIR   := $(PREFIX)/bin
LIBDIR   := $(PREFIX)/lib/csm

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
	@mkdir -p $(BINDIR) $(LIBDIR)
	install -m 755 csm $(LIBDIR)/csm
	install -m 644 util.py $(LIBDIR)/util.py
	ln -sf $(LIBDIR)/csm $(BINDIR)/csm
	@echo ""
	@echo "Installed to $(LIBDIR)/, linked $(BINDIR)/csm"
	@echo "Make sure $(BINDIR) is in your PATH."

uninstall:
	rm -f $(BINDIR)/csm
	rm -rf $(LIBDIR)
	@echo "Removed $(BINDIR)/csm and $(LIBDIR)/"

test:
	./csm --list -n 10
