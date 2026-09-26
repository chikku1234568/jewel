/**
 * Persistent banner required by the problem statement:
 * "A line on the page that this is not for clinical use."
 */
export function NotForClinicalUseBanner() {
  return (
    <div className="banner" role="alert">
      <strong>Not for clinical use.</strong> This is a technical showcase with a
      synthetic patient. It is not a medical device and not clinical advice.
    </div>
  )
}
