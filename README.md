These are tests for this [PR](https://github.com/algorand/go-algorand/pull/6057) that adds pooling of logic signatures size budget across a transaction group to Algorand.

We test both `goal clerk dryrun` and actually sending transactions, for both single transactions and groups, testing success and failure.

To run the test you need to:
1) recompile the goal binary with the PR source code (by running `make` from the PR repo main folder)
2) start a local private network
3) edit the private network configuration at the top of [devnet.py](https://github.com/giuliop/test-lsig-size-pooling/blob/main/devnet.py)
4) run the script at [test.py](https://github.com/giuliop/test-lsig-size-pooling/blob/main/test.py); e.g. if using [pipenv](https://pipenv.pypa.io/) to manage virtual envs with `pipenv run python test.py`
