"use client";

import { ModernSelect } from "../../components/ui/ModernSelect";
import { formatMoney } from "../../lib/formatting";
import { AccountItem, BankItem } from "../../lib/types";

type Props = {
  accounts: AccountItem[];
  banks?: BankItem[];
  name?: string;
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  includeEmpty?: boolean;
  emptyLabel?: string;
  excludeAccountId?: number;
  bankId?: number | string;
  showBalance?: boolean;
};

export function flattenAccounts(accounts: AccountItem[], bankId?: number | string, excludeAccountId?: number) {
  const active = accounts
    .filter((account) => account.is_active !== false)
    .filter((account) => !bankId || account.bank_id === Number(bankId))
    .filter((account) => account.id !== excludeAccountId);
  const byParent = new Map<number | null, AccountItem[]>();
  active.forEach((account) => {
    const parent = account.parent_account_id ?? null;
    byParent.set(parent, [...(byParent.get(parent) || []), account]);
  });
  byParent.forEach((items) => items.sort((a, b) => (a.display_order || 0) - (b.display_order || 0) || a.name.localeCompare(b.name)));
  const output: Array<AccountItem & { depth: number }> = [];
  const visit = (parentId: number | null, depth: number, seen = new Set<number>()) => {
    for (const account of byParent.get(parentId) || []) {
      if (seen.has(account.id)) continue;
      output.push({ ...account, depth });
      const nextSeen = new Set(seen);
      nextSeen.add(account.id);
      visit(account.id, depth + 1, nextSeen);
    }
  };
  visit(null, 0);
  active
    .filter((account) => account.parent_account_id && !active.some((parent) => parent.id === account.parent_account_id))
    .forEach((orphan) => {
      if (!output.some((account) => account.id === orphan.id)) output.push({ ...orphan, depth: 0 });
    });
  return output;
}

export function AccountSelector({
  accounts,
  banks = [],
  name = "account_id",
  value,
  defaultValue,
  onValueChange,
  placeholder = "Select account",
  required,
  disabled,
  includeEmpty,
  emptyLabel = "No linked account",
  excludeAccountId,
  bankId,
  showBalance = false,
}: Props) {
  const bankName = (id: number) => banks.find((bank) => bank.id === id)?.name;
  const flattened = flattenAccounts(accounts, bankId, excludeAccountId);
  const options = flattened.map((account) => {
    const prefix = account.depth > 0 ? `${"— ".repeat(account.depth)}` : "";
    const details = [account.account_type || account.type, bankName(account.bank_id), showBalance ? formatMoney(account.current_balance, account.currency) : ""]
      .filter(Boolean)
      .join(" · ");
    return {
      value: String(account.id),
      label: `${prefix}${account.name}${details ? ` · ${details}` : ""}`,
    };
  });
  return (
    <ModernSelect
      name={name}
      value={value}
      defaultValue={defaultValue}
      onValueChange={onValueChange}
      required={required}
      disabled={disabled || options.length === 0}
      placeholder={options.length ? placeholder : "No accounts yet"}
      options={[...(includeEmpty ? [{ value: "", label: emptyLabel }] : []), ...options]}
    />
  );
}
