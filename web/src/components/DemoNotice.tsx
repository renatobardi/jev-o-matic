export function DemoNotice() {
  return (
    <p className="notice" role="note">
      <strong>Lab demo.</strong> Measured on 29 real PRs labeled by an AI (not by human reviewers): the cascade picked the same lane as the labeler in 20 and never asked for less review than it did. Small sample; do not use it as a real gate.
    </p>
  );
}
