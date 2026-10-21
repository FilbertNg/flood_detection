# Resident swipe home: open on my street, swipe between saved streets

Branch `feat/resident-swipe-home`, stacked on `feat/resident-street-sky` (the weather-style street page is not on `main` yet). Frontend only: no API, contract or `packages/shared` change, no new dependency.

## Routes

| Path | Shows |
|---|---|
| `/` | No saved streets: `FindStreet` start screen. Otherwise the pager. |
| `/street/:id` | Saved: the pager on that street. Not saved: one `StreetView` with "+ Add to my streets". Push clicks land here. |
| `/map` | The old `HomePage` (map, summary, credits) plus a back link to `/`. |
| `/streets` | The picker; after saving it returns to `/`. |
| `/report` | Unchanged. |

`/` and `/street/:id` are children of one layout route (`SwipeShell`), so changing the URL on a swipe (`navigate(..., { replace: true })`) keeps the pager mounted and its scroll position.

## Pieces

1. `components/StreetView.tsx`: the old `StreetPage` body. `active=false` stops the sky animation (one still frame) and the 10 s refetch. `routes/Street.tsx` keeps a thin wrapper.
2. `lib/order.ts`: `orderStreets(saved, levels)`: Danger, Warning, Watch, Normal; saved order within a level. The order is frozen while the pager is open so pages never jump under the resident's finger; it is recomputed when the saved list changes or the pager reopens.
3. `routes/SwipeHome.tsx`: CSS scroll-snap pager; only the active panel and its neighbours are mounted; `IntersectionObserver` (0.6) tracks the active panel; arrow keys move; reduced motion jumps. Opens on the requested street, else the first panel when one is alerting, else the last viewed (sessionStorage), else the first.
4. `components/BottomBar.tsx`: glass bar with the map button, page dots (alert colour at Warning/Danger, aria labels) and the list button.
5. `routes/FindStreet.tsx` + `nearestStreet()` in `lib/geo.ts`: location asked only on tap; nearest street computed on the phone from `api.streets()` geometry; more than 1 km away means outside BBR.
6. App shell: `/` and `/street/:id` are full screen; Back in the street view is replaced by the bottom bar.

## Tests (written first)

`lib/order`, `lib/geo` (`nearestStreet` with the committed `assets/geo/bbr_streets.geojson` and the mocks), `BottomBar` dots, `SwipeHome` (order, open-on rules, saved and unsaved `/street/:id`), `FindStreet` (no saved streets, location found, outside BBR, denied), `PickStreets` returning to `/`, `Home` back link.
