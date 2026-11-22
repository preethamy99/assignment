import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import {
  AbstractControl,
  FormArray,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  ValidationErrors,
  ValidatorFn,
  Validators,
} from '@angular/forms';

import { AuthService, LoginCredentials } from './auth.service';
import {
  MAX_PACKAGES,
  PackageImportError,
  readPackagesFromFile,
} from './package-import';
import { PackedBox, PackageInput } from './package.model';
import { buildAssignmentsCsv } from './packing-assignments';
import { PackingApiService } from './packing-api.service';

type PackageControls = {
  id: FormControl<number>;
  width: FormControl<number>;
  height: FormControl<number>;
  length: FormControl<number>;
  weight: FormControl<number>;
};

type PackageRow = FormGroup<PackageControls>;

const integerValidator: ValidatorFn = (
  control: AbstractControl,
): ValidationErrors | null =>
  Number.isInteger(control.value) ? null : { integer: true };

const positiveValidator: ValidatorFn = (
  control: AbstractControl,
): ValidationErrors | null =>
  Number(control.value) > 0 ? null : { positive: true };

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App {
  readonly auth = inject(AuthService);
  private readonly packingApi = inject(PackingApiService);

  readonly packages = new FormArray<PackageRow>([]);
  readonly packageForm = new FormGroup({ packages: this.packages });
  readonly loginForm = new FormGroup({
    email: new FormControl('test@example.com', {
      nonNullable: true,
      validators: [Validators.required, Validators.email],
    }),
    password: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required],
    }),
  });
  readonly isLoggingIn = signal(false);
  readonly isSubmitting = signal(false);
  readonly isImporting = signal(false);
  readonly result = signal<number | null>(null);
  readonly boxes = signal<PackedBox[]>([]);
  readonly errorMessage = signal('');
  readonly importErrorMessage = signal('');
  readonly importSuccessMessage = signal('');

  constructor() {
    this.addPackage({ id: 123, width: 10, height: 10, length: 10, weight: 5 });
    this.addPackage({ id: 125, width: 5, height: 5, length: 10, weight: 10 });
    this.packageForm.valueChanges.subscribe(() => this.clearResult());
  }

  get canAddPackage(): boolean {
    return this.packages.length < MAX_PACKAGES;
  }

  get canImportPackages(): boolean {
    return this.canAddPackage && !this.isImporting() && !this.isSubmitting();
  }

  addPackage(
    value: PackageInput = {
      id: this.nextPackageId(),
      width: 10,
      height: 10,
      length: 10,
      weight: 5,
    },
  ): void {
    if (!this.canAddPackage) {
      return;
    }

    this.packages.push(this.createPackageRow(value));
    this.clearResult();
    this.clearImportMessages();
  }

  removePackage(index: number): void {
    this.packages.removeAt(index);
    this.clearResult();
    this.clearImportMessages();
  }

  async importPackages(event: Event): Promise<void> {
    const target = event.currentTarget;
    if (!(target instanceof HTMLInputElement)) {
      this.importErrorMessage.set('Could not read the selected file.');
      return;
    }

    const file = target.files?.[0];
    target.value = '';
    if (!file) {
      return;
    }

    this.importErrorMessage.set('');
    this.importSuccessMessage.set('');
    if (!this.canAddPackage) {
      this.importErrorMessage.set(
        `A maximum of ${MAX_PACKAGES} packages can be added.`,
      );
      return;
    }

    this.isImporting.set(true);
    try {
      const importedPackages = await readPackagesFromFile(file);
      if (this.packages.length + importedPackages.length > MAX_PACKAGES) {
        throw new PackageImportError(
          `This import would exceed the ${MAX_PACKAGES}-package limit.`,
        );
      }

      importedPackages.forEach((value) =>
        this.packages.push(this.createPackageRow(value)),
      );
      this.clearResult();
      this.importSuccessMessage.set(
        `Added ${importedPackages.length} packages from ${file.name}.`,
      );
    } catch (error: unknown) {
      this.importErrorMessage.set(
        error instanceof PackageImportError
          ? error.message
          : 'Could not read this file. Check that it is a valid, unprotected spreadsheet.',
      );
    } finally {
      this.isImporting.set(false);
    }
  }

  login(): void {
    this.loginForm.markAllAsTouched();
    if (this.loginForm.invalid) {
      this.errorMessage.set('Enter a valid email address and password.');
      return;
    }

    this.isLoggingIn.set(true);
    this.errorMessage.set('');
    const credentials: LoginCredentials = this.loginForm.getRawValue();
    this.auth.login(credentials).subscribe({
      next: () => {
        this.loginForm.controls.password.setValue('');
        this.isLoggingIn.set(false);
      },
      error: (error: unknown) => {
        this.errorMessage.set(this.describeError(error, true));
        this.isLoggingIn.set(false);
      },
    });
  }

  logout(): void {
    this.auth.logout();
    this.clearResult();
  }

  calculateBoxes(): void {
    if (!this.auth.isAuthenticated()) {
      this.errorMessage.set('Sign in before calculating boxes.');
      return;
    }
    this.packageForm.markAllAsTouched();

    if (this.packageForm.invalid) {
      this.errorMessage.set('Check the highlighted fields before calculating.');
      return;
    }

    this.isSubmitting.set(true);
    this.errorMessage.set('');
    this.result.set(null);
    this.boxes.set([]);

    const packages = this.packages.controls.map((row) => row.getRawValue());
    this.packingApi.calculate(packages).subscribe({
      next: (response) => {
        this.result.set(response.box_count);
        this.boxes.set(response.boxes);
        this.isSubmitting.set(false);
      },
      error: (error: unknown) => {
        this.errorMessage.set(this.describeError(error, false));
        if (error instanceof HttpErrorResponse && error.status === 401) {
          this.auth.logout();
        }
        this.isSubmitting.set(false);
      },
    });
  }

  downloadAssignments(): void {
    const boxes = this.boxes();
    if (boxes.length === 0) {
      return;
    }

    const blob = new Blob([buildAssignmentsCsv(boxes)], {
      type: 'text/csv;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'packing-assignments.csv';
    document.body.appendChild(link);
    link.click();
    link.remove();
    globalThis.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  private createPackageRow(value: PackageInput): PackageRow {
    return new FormGroup<PackageControls>({
      id: new FormControl(value.id, {
        nonNullable: true,
        validators: [Validators.required, integerValidator],
      }),
      width: new FormControl(value.width, {
        nonNullable: true,
        validators: [Validators.required, positiveValidator],
      }),
      height: new FormControl(value.height, {
        nonNullable: true,
        validators: [Validators.required, positiveValidator],
      }),
      length: new FormControl(value.length, {
        nonNullable: true,
        validators: [Validators.required, positiveValidator],
      }),
      weight: new FormControl(value.weight, {
        nonNullable: true,
        validators: [Validators.required, Validators.min(0)],
      }),
    });
  }

  private nextPackageId(): number {
    return this.packages.controls.reduce(
      (largestId, row) => Math.max(largestId, row.controls.id.value),
      0,
    ) + 1;
  }

  private clearResult(): void {
    this.result.set(null);
    this.boxes.set([]);
    this.errorMessage.set('');
  }

  private clearImportMessages(): void {
    this.importErrorMessage.set('');
    this.importSuccessMessage.set('');
  }

  private describeError(error: unknown, isLogin: boolean): string {
    if (!(error instanceof HttpErrorResponse)) {
      return 'Something went wrong while communicating with the API.';
    }

    if (error.status === 0) {
      return 'Could not reach the API. Make sure the backend is running.';
    }
    if (error.status === 401) {
      return isLogin
        ? 'Email or password is incorrect.'
        : 'Your session expired. Sign in again.';
    }
    if (error.status === 503) {
      return 'Authentication is not configured on the backend.';
    }

    const detail: unknown = error.error?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (
      typeof detail === 'object' &&
      detail !== null &&
      'message' in detail &&
      typeof detail.message === 'string'
    ) {
      return detail.message;
    }

    return 'Check the submitted details and try again.';
  }
}
