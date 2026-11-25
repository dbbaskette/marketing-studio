# Rolling restarts

## 1. Rolling restarts

What they do, and when capacity holds

Notes: 1 min. Welcome, and what is assumed.

## 2. A rolling restart replaces instances one batch at a time

Understand: Instances are replaced in batches while the app keeps serving.

- **Batch**: Instances are replaced one batch at a time.
- **Traffic**: The app keeps serving while it restarts.

Source: Platform documentation: restarts

Notes: 6 min. Walk the three-instance example.

## 3. Capacity holds only with more than one instance

Understand: A single instance has nothing to hold capacity while it restarts.

- **Several**: The others carry the load.
- **One**: Requests are dropped while it restarts.

Caveat: A single-instance app still drops requests while it restarts.

Notes: 7 min. Health checks start the next batch.

## 4. Rolling does not always mean zero downtime

Understand: The claim is true only for an app with several instances.

- **Claim**: Rolling always means zero downtime.
- **Correction**: Only with more than one instance.

Notes: 7 min. Correct the claim without dismissing the customer.

## 5. Check what you can now explain

Understand: Each question checks one point.

- **Describe**: What happens to the instances?
- **Explain**: Why does one instance lose capacity?

Notes: 3 min. One question for each point.

## 6. Health checks start the next batch

Understand: The next batch waits for the last one to report healthy.

- **Health first**: A batch is replaced only once the last one is healthy.
- **Wait**: A failing check holds the restart.

Notes: 4 min. Show the check in the log.

## 7. A failed batch is rolled back, not pushed on

Understand: A batch that fails its check is put back as it was.

- **Roll back**: The failed batch returns to the last version.
- **Push on**: Carrying on would take capacity down.

Notes: 3 min. One example.

## 8. Next: try it on a test app

Notes: 1 min. Point to the sandbox.
