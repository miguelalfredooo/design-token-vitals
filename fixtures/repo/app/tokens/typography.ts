// A JS token layer spells the concept `fontFamily`. normalize() lowercases
// it to `fontfamily`, so a selector reading the concept id cannot see the
// word boundary — the case that made a product's own typeface invisible.
export const typography = Object.freeze({
  fontFamily: {
    sans: ['"Fixture Sans"', 'ui-sans-serif', 'sans-serif'],
  },
  fontWeight: { medium: '500' },
})
