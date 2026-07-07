export type Dashboard = {
  net_worth: number;
  total_liquidity: number;
  total_investments: number;
  insurance_value: number;
  total_debt: number;
  monthly_income: number;
  monthly_expenses: number;
  savings_rate: number;
  recent_transactions: Array<{ id: number; date: string; description: string; amount: number; currency: string }>;
  account_balances: Array<{ id: number; bank_id: number; name: string; type: string; current_balance: number; currency: string }>;
  card_balances: Array<{ id: number; bank_id: number; account_id: number; name: string; type: string; current_balance: number; last4: string }>;
};

export type UserSettings = {
  theme: "system" | "light" | "dark";
  favorite_language: string;
  default_currency: string;
  date_format: string;
  number_format: string;
  profile_photo_url?: string | null;
  notifications_enabled: boolean;
};

export type BankItem = { id: number; name: string; country?: string };

export type AccountItem = {
  id: number;
  bank_id: number;
  parent_account_id?: number | null;
  name: string;
  type: string;
  account_type?: string;
  account_level?: number;
  currency: string;
  opening_balance?: number;
  current_balance: number;
  display_order?: number;
};

export type CardItem = {
  id: number;
  bank_id: number;
  account_id: number;
  name: string;
  type: string;
  last4: string;
  current_balance: number;
  credit_limit?: number | null;
  expiry_month?: number | null;
  expiry_year?: number | null;
};

export type CategoryItem = {
  id: number;
  user_id?: number | null;
  name: string;
  type: "income" | "expense" | "investment";
  color?: string | null;
  is_system: boolean;
};

export type TransactionItem = {
  id: number;
  bank_id: number;
  account_id: number;
  card_id?: number;
  category_id?: number;
  type: string;
  source?: string;
  date: string;
  description: string;
  amount: number;
  currency: string;
};

export type Profile = { id: number; email: string; full_name: string };
