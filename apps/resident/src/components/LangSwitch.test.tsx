import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LangSwitch } from './LangSwitch';

afterEach(cleanup);

describe('LangSwitch', () => {
  it('shows both languages and marks the current one as pressed', () => {
    render(<LangSwitch lang="en" onChange={() => {}} />);
    const group = screen.getByRole('group', { name: 'Language / Bahasa' });
    expect(within(group).getByRole('button', { name: 'English' })).toHaveAttribute('aria-pressed', 'true');
    expect(within(group).getByRole('button', { name: 'Bahasa Melayu' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('switches only when the other language is chosen', () => {
    const onChange = vi.fn();
    render(<LangSwitch lang="ms" onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: 'Bahasa Melayu' }));
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'English' }));
    expect(onChange).toHaveBeenCalledWith('en');
  });
});
