import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
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

import { PackageInput } from './package.model';
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
  private readonly packingApi = inject(PackingApiService);

  readonly packages = new FormArray<PackageRow>([]);
  readonly packageForm = new FormGroup({ packages: this.packages });
  readonly apiToken = new FormControl('', {
    nonNullable: true,
    validators: [Validators.required],
  });
  readonly isSubmitting = signal(false);
  readonly result = signal<number | null>(null);
  readonly errorMessage = signal('');

  constructor() {
    this.addPackage({ id: 123, width: 10, height: 10, length: 10, weight: 5 });
    this.addPackage({ id: 125, width: 5, height: 5, length: 10, weight: 10 });
    this.packageForm.valueChanges.subscribe(() => this.clearResult());
    this.apiToken.valueChanges.subscribe(() => this.clearResult());
  }

  get canAddPackage(): boolean {
    return this.packages.length < 20;
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
  }

  removePackage(index: number): void {
    this.packages.removeAt(index);
    this.clearResult();
  }

  calculateBoxes(): void {
    this.apiToken.markAsTouched();
    this.packageForm.markAllAsTouched();

    if (this.apiToken.invalid || this.packageForm.invalid) {
      this.errorMessage.set('Check the highlighted fields before calculating.');
      return;
    }

    this.isSubmitting.set(true);
    this.errorMessage.set('');
    this.result.set(null);

    const packages = this.packages.controls.map((row) => row.getRawValue());
    this.packingApi.calculate(packages, this.apiToken.value).subscribe({
      next: (response) => {
        this.result.set(response.box_count);
        this.isSubmitting.set(false);
      },
      error: (error: unknown) => {
        this.errorMessage.set(this.describeError(error));
        this.isSubmitting.set(false);
      },
    });
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
    this.errorMessage.set('');
  }

  private describeError(error: unknown): string {
    if (!(error instanceof HttpErrorResponse)) {
      return 'Something went wrong while calculating boxes.';
    }

    if (error.status === 0) {
      return 'Could not reach the API. Make sure the backend is running.';
    }
    if (error.status === 401) {
      return 'The API token is invalid. Check it and try again.';
    }
    if (error.status === 503) {
      return 'The backend API token is not configured.';
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

    return 'Check the package details and try again.';
  }
}
