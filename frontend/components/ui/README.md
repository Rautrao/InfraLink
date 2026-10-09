# Public UI kit

The resident portal's shared controls live in `frontend/components/ui`. Import them from `@/components/ui` so the portal and staff pages use the same touch sizes, focus rings, status meanings, loading states and date language.

## Components

- `Button` supports `primary`, `secondary`, `quiet` and `danger` tones. The default minimum touch height is 44 px.
- `Input`, `Select`, `Textarea` apply the shared accessible field style. Pair every field with a visible `<label>`.
- `Card` is the standard bordered content surface.
- `Badge` is for small derived flags. `StatusChip` always renders a symbol and a text label. Supported status classes are `planned`, `permitted`, `ongoing`, `paused`, `completed`, `restoration_verified`, `closed`, `delayed` and `update_overdue`. Pass `label` to use the active language.
- `Tabs` accepts `{ id, label }[]`, a selected `value`, and `onChange`.
- `Modal` and `Drawer` are controlled with `open`, `title`, `children` and `onClose`. Modal closes on Escape and backdrop click.
- `ToastProvider` is mounted by the root app providers. Call `toast(message)` from `@/components/ui` to show a short live announcement.
- `Skeleton`, `EmptyState` and `ErrorState` cover loading, no-results and retry states.
- `LastUpdated` accepts an ISO timestamp and uses the selected English/Hindi locale, relative time, and an absolute `en-IN` or `hi-IN` date.
- `Timeline` accepts `{ id?, title, detail?, date?, by? }[]`.
- `ProgressBar` accepts a percentage `value` and optional `label`.
- `Pagination` accepts `page`, `pageSize`, `total` and `onPage(nextPage)`.
- `MapView` accepts a GeoJSON `FeatureCollection`, `onSelect(feature)`, `onBoundsChange(bbox)`, `fitToken` and `height`. It renders OSM raster tiles, work lines/areas, delayed dashed lines, zoom and geolocation controls, clusters and a reset control. Import MapLibre CSS once in the root layout.

## Example

```tsx
import { Button, Card, LastUpdated, StatusChip } from '@/components/ui';

<Card>
  <StatusChip status="ongoing" label="Ongoing" />
  <LastUpdated value="2026-10-07T10:42:00Z" />
  <Button tone="secondary">Open work</Button>
</Card>
```

Use `useT()` from `@/lib/i18n` for resident-facing text and date formatting. Keep icon-plus-text labels on status chips; colour is supplementary.
