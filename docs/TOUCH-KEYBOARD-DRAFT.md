# PiCalendar 0.5.5: native touch keyboard draft

Status: implementation scaffold, not a validated release. Baseline: branch 0.5.0,
commit 7e0af025962b119b49a8cdbd82160accebf8178c. No version bump yet.

## Design

Reuse wvkbd-deskintl as the native keyboard. The supervisor requires advertised
layer-shell, virtual-keyboard, input-method-v2, and text-input-v3 interfaces and a
wvkbd binary advertising --auto and --hidden. It starts the keyboard hidden and
lets native input-method activation/deactivation drive visibility. These checks
are necessary, not proof of browser compatibility. Another input method may
already own the seat even when these checks pass.

The opt-in launcher supervises the keyboard and the existing run-kiosk.sh.
The only change to run-kiosk.sh is conditional Chromium IME flags. Its startup
helper, URL, browser selection and existing flags remain intact. The supervisor
stops both process groups on exit or failure and prevents duplicate sessions.
The keyboard runs as the session user without root or uinput access.

## Files

- tools/touch_keyboard.py: capability checks and process supervision.
- run-kiosk-touch.sh: opt-in entry point.
- run-kiosk.sh: existing launcher plus conditional IME flags.
- install-touch-keyboard-draft.sh: dependency installer only.
- tests/test_touch_keyboard_draft.py: eight standard-library unit tests.

## Try on a Raspberry Pi 5

Apply these draft files only to a working copy of branch 0.5.5. Back up the
existing launcher first. Do not overwrite local customizations without reviewing
the diff. Do not run two kiosks at once.

    bash install-touch-keyboard-draft.sh
    python3 -m unittest discover -s tests -p 'test_touch_keyboard_draft.py'
    python3 tools/touch_keyboard.py --check
    bash run-kiosk-touch.sh

Run capability checks and the launcher inside the actual kiosk Wayland session,
not through a bare SSH session or sudo. The supervisor defaults to wvkbd-deskintl.
To test another available build:

    python3 tools/touch_keyboard.py --binary wvkbd-mobintl --check
    python3 tools/touch_keyboard.py --binary wvkbd-mobintl --height 300 -- bash run-kiosk.sh

The package provided by your OS may lack automatic activation. The installer
never downloads/builds an unpinned upstream checkout. If the package is too old,
a reviewed, pinned wvkbd build is still needed before deployment.

## Cage and deployment gate

Do not assume stock Cage implements these protocols. If the check reports missing
interfaces, this draft deliberately refuses to start the touch kiosk. It does
not silently display a permanently visible keyboard or pretend local HTML inputs
provide Google login support. Required follow-up is either a reviewed Cage fork
with the necessary protocol implementation or a minimal standalone compositor
such as labwc/Sway, after checking that installed version's capabilities. A full
desktop is not required by the design, but no new compositor session is installed
or enabled by this draft. The existing installer remains untouched.

After all hardware acceptance tests pass, replace the existing autostart command
with the touch launcher (do not add a duplicate). Automated autostart migration,
compositor configuration and rollback remain work for the integration phase.

## Password handling

No DOM injection, credential reads, key-event HTTP endpoint, clipboard bridge,
remote debugging, or output capture is used. The supervisor removes WAYLAND_DEBUG
and WVKBD_DEBUG, never passes wvkbd key-output/debug switches, and discards the
keyboard's stdout/stderr. Do not enable tracing or record real credentials in
test results. This does not audit Chromium's existing password-store policy or
prove wvkbd's handling of every password field. Those require separate review.

## Acceptance checklist: not yet run on hardware

Use a test account, and never attach credentials or protocol traces to reports.

- Boot with the existing startup animation; open Settings entirely by touch.
- Focus every input type and editable region; verify automatic opening.
- Blur, close dialogs, submit forms and navigate away; verify dismissal.
- Verify numbers, punctuation, special characters, Shift, Caps Lock, Backspace,
  Enter, Space, selection and editing. Confirm the installed layout actually
  provides all required controls rather than assuming its default is sufficient.
- Test Google email/password pages, account selection, consent and any MFA flow;
  ensure masking remains intact and Google synchronization still completes.
- Test Google authentication popups/new windows as well as same-window redirects.
- Create/edit calendar events, including time/date pickers, with no hardware keys.
- Verify bottom positioning and that focused fields remain visible in Settings,
  event dialogs and Google's pages in both display orientations.
- Test sleep with keyboard open, sleep with keyboard closed, and double-tap wake.
- Verify hidden cursor, calendar navigation, boot behavior and synchronization.
- Stop the kiosk and verify its keyboard exits; test keyboard crash cleanup.

## Known unfinished requirements

Focus-driven visibility is delegated to the native protocol and needs end-to-end
testing. There is no explicit Done button or application sleep hook in this draft.
No promise is made that fullscreen Chromium respects the keyboard's exclusive
zone; resizing/scrolling must be measured and may need browser/compositor changes.
No layout/theme customization or automatic compositor migration is implemented.
The eight unit tests cover parsing, command safety, height bounds, environment
sanitization and rejection of missing/old dependencies, not actual touch input,
OAuth, process-group teardown or UI regressions. This is not success-criteria
completion and must not be presented as a working Cage release.

## Upstream references

https://github.com/jjsullivan5196/wvkbd
https://github.com/jjsullivan5196/wvkbd/blob/master/main.c
https://github.com/cage-kiosk/cage
https://wayland.app/protocols/input-method-unstable-v2
https://wayland.app/protocols/text-input-unstable-v3
