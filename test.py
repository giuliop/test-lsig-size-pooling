#!/usr/bin/env python3
import os
import subprocess

import algosdk as sdk
from algosdk import atomic_transaction_composer as atc

import devnet as dev

should_have_failed = "This should have failed"

long_lsig_teal = f"""
#pragma version 10
{'byte 0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\npop\n' * 1000}
int 1
"""

short_lsig_teal = f"""
#pragma version 10
int 1
"""

long_lsig = dev.compile(long_lsig_teal)
long_lsig_address = sdk.logic.address(long_lsig)
print(f"Long lsig has size of {len(long_lsig)} bytes, and address "
      f"{long_lsig_address}\n")
# Size: 2033 bytes

short_lsig = dev.compile(short_lsig_teal)
short_lsig_address = sdk.logic.address(short_lsig)
print(f"Short lsig has size of {len(short_lsig)} bytes, and address "
        f"{short_lsig_address}\n")
# Size: 3 bytes

dev.fund(long_lsig_address, 1_000_000)
dev.fund(short_lsig_address, 1_000_000)

temp_file = "temp.txn"
dryrun_cmd = ['goal', 'clerk', 'dryrun', '-t', temp_file, '-P', 'future']

def main():
    """Run all tests"""
    test_single_lsig()
    test_group()
    os.remove(temp_file)

def test_single_lsig():
    """Test a too large lsig which fails, then a small lsig which passes.
       We test clerk dryrun first, then actually sending the transaction.
    """

    print("Trying to send a single lsig transaction over the 1000kb limit")
    txn = make_lsig_txn(long_lsig)
    sdk.transaction.write_to_file([txn], temp_file)

    # test dryrun first, then test sending the transaction
    result = subprocess.run(
            dryrun_cmd,
            capture_output=True, text=True,
    )
    assert result.stderr == "total lsigs size too large: 2033 > 1000\n"

    func = lambda: dev.algod.send_transaction(txn)
    validate_expected_error(func, "more than the available pool of 1000 bytes")

    print("Trying to send a single lsig transaction under the 1000kb limit")
    txn = make_lsig_txn(short_lsig)
    sdk.transaction.write_to_file([txn], temp_file)

    # test dryrun first, then test sending the transaction
    result = subprocess.run(
            dryrun_cmd,
            capture_output=True, text=True, check=True,
    )

    dev.algod.send_transaction(txn)
    print("Success !\n")

def test_group():
    """Test a group that exceeds pooling budget, then a group with enough pooling
       budget. We test clerk dryrun first, then actually sending the transactions.
    """

    print("Trying to send a group over the lsig size pool limit")
    group = atc.AtomicTransactionComposer()
    group.add_transaction(make_fee_cover_txn())
    long_lsig_txn = make_lsig_txn_with_signer(long_lsig)
    group.add_transaction(long_lsig_txn)

    # test dryrun first, then test sending the transaction
    txns = [signed_txn_from_txn_with_signer(txn) for txn in group.txn_list]
    sdk.transaction.write_to_file(txns, temp_file)
    result = subprocess.run(
            dryrun_cmd,
            capture_output=True, text=True,
    )
    assert result.stderr == "total lsigs size too large: 2033 > 2000\n"

    func = lambda: group.execute(dev.algod, 4)
    validate_expected_error(func, "more than the available pool of 2000 bytes")

    print("Now trying pooling with enough size budget")
    group = atc.AtomicTransactionComposer()
    group.add_transaction(make_fee_cover_txn())
    long_lsig_txn = make_lsig_txn_with_signer(long_lsig)
    group.add_transaction(long_lsig_txn)
    for txn in make_dummy_lsig_txns_with_signer(2):
        group.add_transaction(txn)

    # test dryrun first, then test sending the transaction
    txns = [signed_txn_from_txn_with_signer(txn) for txn in group.txn_list]
    sdk.transaction.write_to_file(txns, temp_file)
    result = subprocess.run(
            dryrun_cmd,
            capture_output=True, text=True, check=True,
    )

    group.execute(dev.algod, 4)
    print("Success !\n")

def make_fee_cover_txn() -> atc.TransactionWithSigner:
    """Create a simple payment transaction that covers the group fee"""
    sp = dev.algod.suggested_params()
    sp.flat_fee = True
    sp.fee = 16 * sp.min_fee
    txn = sdk.transaction.PaymentTxn(dev.pk, sp, dev.pk, 0)
    return atc.TransactionWithSigner(txn, atc.AccountTransactionSigner(dev.sk))

def make_lsig_txn(lsig: bytes) -> sdk.transaction.LogicSigTransaction:
    """Create a 0-algo payment transaction signed by the given lsig"""
    lsig_address = sdk.logic.address(lsig)
    sp = dev.algod.suggested_params()
    txn = sdk.transaction.PaymentTxn(lsig_address, sp, lsig_address, 0)
    lsig_account = sdk.transaction.LogicSigAccount(lsig)
    return sdk.transaction.LogicSigTransaction(txn, lsig_account)

def make_lsig_txn_with_signer(lsig: bytes, zeroFee: bool=False) -> atc.TransactionWithSigner:
    """Create a 0-algo payment transaction signed by the given lsig"""
    lsig_address = sdk.logic.address(lsig)
    sp = dev.algod.suggested_params()
    if zeroFee:
        sp.flat_fee = True
        sp.fee = 0
    txn = sdk.transaction.PaymentTxn(lsig_address, sp, lsig_address, 0)
    lsig_account = sdk.transaction.LogicSigAccount(lsig)
    lsig_signer = atc.LogicSigTransactionSigner(lsig_account)
    return atc.TransactionWithSigner(txn, lsig_signer)

def make_dummy_lsig_txns_with_signer(n: int) -> list[atc.TransactionWithSigner]:
    """Create n distinct dummy lsig transactions with zero fee for pooling purposes"""
    txns = []
    for i in range(n):
        lsig_teal = f"#pragma version 10\nint {i}\npop\nint 1\n"
        lsig = dev.compile(lsig_teal)
        txn_with_signer = make_lsig_txn_with_signer(lsig, zeroFee=True)
        txns.append(txn_with_signer)
    return txns

def signed_txn_from_txn_with_signer(txn_with_signer: atc.TransactionWithSigner) -> sdk.transaction.SignedTransaction:
    txn = txn_with_signer.txn
    signer = txn_with_signer.signer
    signed_txn = signer.sign_transactions([txn], [0])[0]
    return signed_txn

def validate_expected_error(func: callable, expected_error: str):
    try:
        func()
        raise Exception("This should have failed")
    except Exception as e:
        if str(e) == "This should have failed" or expected_error not in str(e):
            raise e
        print(f"Failed as expected with error: {e}\n")


if __name__ == "__main__":
    main()