---
name: CEO Newsroom
description: The established green newsroom, extended to personal account and settings surfaces.
colors:
  bg: "#101211"
  panel: "#171a17"
  border: "#292d28"
  muted: "#858b81"
  accent: "#c6e9a8"
  text: "#dedfd9"
  heading: "#f0eee4"
  field: "#1a2415"
  field-border: "#48593c"
  field-text: "#e3ecd9"
typography:
  headline:
    fontFamily: "Instrument Serif, Georgia, serif"
    fontWeight: 400
  title:
    fontFamily: "Instrument Serif, Georgia, serif"
    fontSize: "29px"
    fontWeight: 400
    lineHeight: 1.2
  body:
    fontFamily: "DM Sans Variable, sans-serif"
    fontWeight: 400
    lineHeight: 1.8
  control:
    fontFamily: "DM Sans Variable, sans-serif"
    fontSize: "12px"
    fontWeight: 400
  field:
    fontFamily: "DM Sans Variable, sans-serif"
    fontSize: "14px"
    fontWeight: 400
rounded:
  compact: "5px"
  control: "6px"
  field: "7px"
  card: "8px"
spacing:
  tight: "8px"
  control-gap: "9px"
  medium: "12px"
  section: "18px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "#2a411b"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "12px 17px"
  button-primary-hover:
    backgroundColor: "#dbf3c7"
    textColor: "#193d00"
  button-secondary:
    backgroundColor: "#181c16"
    textColor: "#b6c1a6"
    rounded: "{rounded.control}"
    padding: "9px 12px"
  input-account:
    backgroundColor: "{colors.field}"
    textColor: "{colors.field-text}"
    typography: "{typography.field}"
    rounded: "{rounded.field}"
    padding: "10px 12px"
  navigation-settings:
    textColor: "#b3c6a0"
    rounded: "{rounded.compact}"
    padding: "9px 3px"
  navigation-settings-selected:
    backgroundColor: "#314723"
    textColor: "#ecf5e3"
  card-membership:
    backgroundColor: "#1b2915"
    textColor: "#c7dbb5"
    rounded: "{rounded.card}"
    padding: "15px 10px"
---

# Design System: CEO Newsroom

## Overview

**Creative North Star: "The established green newsroom"**

CEO Newsroom pairs editorial serif headings with quiet sans-serif controls, pale green emphasis and deep forest surfaces. The existing CEO artwork and green identity are durable product commitments. Account access and settings inherit this language; they do not introduce a separate brand.

This record describes the incumbent foundation and the completed account/settings extension, including profile, password and billing utilities, derived from `frontend/src/styles.css`, `frontend/src/account.css`, `AccountAccess.tsx`, `AccountSettings.tsx`, `ProfileSettings.tsx` and `BillingHistory.tsx`. It is not a blanket endorsement of every legacy feed detail. The scoped extension had no concept seed or generated composition.

**Key Characteristics:**

- Instrument Serif headlines and DM Sans reading and control text.
- Pale green actions against low-glare forest surfaces.
- Fine borders and tonal changes establish hierarchy.
- Small, softly rounded controls and circular presenter artwork.
- Explicit selection, keyboard focus, status and simulation disclosure.

## Colors

One green identity spans light editorial material and dark interactive surfaces; warm light text softens the contrast.

### Primary

- **Pale green accent:** primary actions, keyboard outlines and active cues use `accent`.
- Account access uses a pale green story region against a dark forest form region. Settings continues the dark forest surface family.

### Neutral

- **Newsroom background and panel:** `bg` and `panel` provide the incumbent dark foundation.
- **Fine divider:** `border` separates neighboring regions without adding weight.
- **Body and heading text:** `text` and `heading` preserve the warm light reading hierarchy; `muted` supports secondary content.
- **Forest fields:** `field`, `field-border` and `field-text` distinguish editable areas from surrounding surfaces.

### Named Rules

**The Green Continuity Rule.** Extend the existing pale green and forest palette across account and settings surfaces.

## Typography

**Display Font:** Instrument Serif, with Georgia and serif fallbacks.

**Body Font:** DM Sans Variable, with sans-serif fallback.

**Character:** Expressive, regular-weight serif headings provide the editorial voice. Sans-serif controls and supporting copy stay direct and restrained; there is no separate account font system.

### Hierarchy

- **Headline:** regular serif, with scale determined by the existing surface. Account access uses a responsive large headline; its form heading is smaller. Mobile reduces both while preserving the serif/sans relationship.
- **Title:** the frontmatter title role is used for account/settings section headings.
- **Body:** account/settings prose uses the body family and generous line-height; principal form copy is (13px), while settings copy is (12px). This is a compact utility surface, not a general mandate to shrink reading content.
- **Controls:** account action and field-label text uses the control role; editable text uses the larger field role.
- **Price:** membership amounts retain the regular serif voice, at (38px) with a compact line-height (1).

### Named Rules

**The Editorial Heading Rule.** Preserve Instrument Serif for major headings and DM Sans for interactive and supporting text.

## Layout

Account access fills the viewport and uses two columns (1.05fr / 1fr): the brand/story region and the centered form region. The form caps at (390px). At the existing mobile breakpoint (760px), the regions stack in reading order, the form cap becomes (440px), and horizontal padding becomes (25px). Preserve normal word spacing when desktop line breaks disappear.

Settings is a right-aligned scrolling drawer, width (490px), capped to the viewport. It uses padding (32px), reduced to (25px 22px) on mobile. Four equal-width native buttons form its section navigation. Membership choices remain a three-column row; payment choices use two columns. Grid children and long account values must shrink or wrap instead of widening the drawer.

Spacing is compact and task-oriented: the observed small gaps in frontmatter serve control groupings, with larger section gaps. Forms use a vertical gap (22px); settings content uses (18px), reducing to (16px) on mobile. These local measurements describe the implemented surfaces rather than an invented universal spacing scale.

Profile editing and password forms use a single-column grid with a gap (16px), reusing the existing field treatment. Native disclosures keep secondary utilities in the same drawer. Billing history uses vertically stacked sections with a gap (20px); invoice and payment-attempt rows use a flexible content column and an auto-sized status column. Invoice links span the row and wrap; renewal confirmation actions also wrap. Preserve these shrinkable columns and wrapping behaviors on narrow screens instead of introducing fixed-width tables.

## Elevation & Depth

Account forms, membership choices and payment choices are flat, with fine strokes and tonal changes. Selection strengthens the border and background instead of lifting the card. The settings drawer separates from the newsroom through a dark translucent backdrop and blur; account/settings components do not introduce decorative shadows.

**The Tonal Selection Rule.** Show selected choices through the existing green background, border and checkmark treatment.

## Shapes

Controls use the compact corner vocabulary in frontmatter: modest rounding rather than pill-shaped primary actions. Inputs and password groups share the field radius; membership cards use the slightly larger card radius. Fine one-pixel borders define fields, cards and section divisions. Presenter portraits retain circular cropping and the supplied artwork.

## Components

### Buttons

Primary buttons are pale green, full-width and plainly labeled. Account/settings actions use a minimum height (43px), with their icon aligned at the far edge. Secondary buttons are dark with a fine green-gray border; contextual actions may hug their content.

Hover changes the background and text. Keyboard focus uses the incumbent accent outline (2px) with an offset (4px). Disabled buttons reduce opacity and use the disabled cursor. Background, text and border transitions last (.18s); reduced-motion preference removes transitions and animation.

### Cards / Containers

Membership cards are selectable buttons with three equal-width choices. Selected cards strengthen the pale green border, deepen the green fill and add a checkmark. Payment-method choices use the same selected-state grammar in a two-column layout, with Lucide icons and text labels. State is conveyed through `aria-pressed` as well as appearance.

### Inputs / Fields

Account inputs and selects use the shared forest field treatment, a fine border, field radius and minimum height (45px). Labels remain visible above fields. Password visibility is a separate labeled icon button inside the grouped field. Its group receives a focus-within outline; the inner input does not add a second outline.

Error messages combine warm tinted text, a dark warm background and a border; success combines a check icon and text. Status must remain readable as content rather than relying solely on color.

Profile editing reuses the account input treatment for the display name and presents the email as wrapping, read-only text. Password changes use three visibly labeled fields inside a disclosure, with a separate text-labeled visibility button. Local save actions use content-sized secondary buttons; the password submission retains the full-width primary treatment. Busy states disable conflicting actions, and saved/error messages use the existing status styles.

### Navigation

The four settings section buttons stay in one equal-width row. The selected section uses the existing green fill and light text. The settings dialog retains Escape dismissal, keyboard focus containment and focus return to its invoking control.

### Utility disclosures

Password and billing utilities use native `details` / `summary` elements with a fine top divider, top padding (18px), and a readable summary (13px) with a minimum height (36px). Opening adds space (18px) between the summary and its contents. Preserve native disclosure semantics and keyboard operation; the drawer's focus handling includes summary controls.

### Billing records and renewal

Invoices and payment attempts use flat, divided lists rather than separate elevated cards. A medium-weight record title sits above quieter metadata; the status remains adjacent as text. Invoice/PDF actions are underlined text links with Lucide icons, a minimum height (32px), and wrapping between actions. Older-record and refresh actions reuse the secondary button style.

Stopping renewal exposes an inline confirmation region using the existing muted green notice material, field radius and padding (14px). The current-period consequence appears before two text-labeled secondary actions: keeping renewal on and confirming the stop. Resume renewal uses a direct secondary action when renewal is already off. These are explicit state transitions within the billing disclosure, not a new dialog or visual identity.

### Presenter and service disclosures

Circular supplied presenter artwork supports the newsroom identity. The independent-reporting / AI-simulated-presenter disclosure remains visible when the account layout stacks. Payment availability and security notes remain explicit content near the related controls; a disabled payment action retains its explanatory status.

## Do's and Don'ts

### Do:

- **Do** preserve the existing green palette, supplied presenter artwork and Instrument Serif / DM Sans pairing.
- **Do** use visible focus, explicit selection states and text alongside status colors.
- **Do** preserve disclosure visibility and normal word spacing when account access stacks on mobile.
- **Do** use flat, bordered account/settings controls with tonal selected states.
- **Do** keep utility disclosures native, billing rows flat and long account values and actions able to wrap.
- **Do** place the billing-period consequence before the explicit renewal-stop confirmation.

### Don't:

- **Don't** create a separate visual identity for account and settings surfaces.
- **Don't** promote unchanged feed eyebrows or tiny legacy labels into rules for new surfaces.
- **Don't** hide simulation or service-status disclosures to shorten a mobile layout.
