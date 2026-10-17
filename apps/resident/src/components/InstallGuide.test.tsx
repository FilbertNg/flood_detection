import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { InstallGuide } from './InstallGuide';

afterEach(cleanup);

describe('InstallGuide', () => {
  it('lists the Add to Home Screen steps in English', () => {
    render(<InstallGuide lang="en" />);
    expect(screen.getAllByRole('listitem')).toHaveLength(4);
    expect(screen.getByText(/Add to Home Screen/)).toBeInTheDocument();
  });
  it('lists the steps in Malay', () => {
    render(<InstallGuide lang="ms" />);
    expect(screen.getByText(/Tambah ke Skrin Utama/)).toBeInTheDocument();
  });
});
